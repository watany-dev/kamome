"""AWS backend implementation."""

from __future__ import annotations

import time
import uuid
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from botocore.exceptions import BotoCoreError, ClientError

from ..config import DEFAULT_LOCAL_ENDPOINT
from ..exceptions import ConfigurationError, ExecutionTimeoutError
from ..model import ExecutionResult
from .base import Backend, StepFunctionsClientProtocol

if TYPE_CHECKING:
    from ..model import ExecutionSpec, StateTestSpec

_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"}
_POLL_INTERVAL_SECONDS = 0.2
_TIMEOUT_STOP_ERROR = "PytestStepFunctions.Timeout"
_TIMEOUT_STOP_CAUSE = "Execution exceeded the configured pytest-stepfunctions timeout."
_MAX_STATE_MACHINE_NAME_LENGTH = 80


class AwsBackend(Backend):
    """Backend for full workflow execution against AWS Step Functions."""

    name = "aws"

    def run(self, spec: ExecutionSpec) -> ExecutionResult:
        _validate_run_spec(spec)

        client = self._service_client()
        state_machine_arn: str | None = None
        execution_arn: str | None = None
        raw: dict[str, Any] = {}

        try:
            create_response = client.create_state_machine(
                name=_ephemeral_state_machine_name(spec.state_machine_name),
                definition=self._json_dump(spec.definition),
                roleArn=spec.config.role_arn,
                type="STANDARD",
            )
            state_machine_arn = str(create_response["stateMachineArn"])
            raw["create_state_machine"] = create_response

            start_response = client.start_execution(
                stateMachineArn=state_machine_arn,
                name=spec.execution_name,
                input=self._json_dump(spec.scenario.input),
            )
            execution_arn = str(start_response["executionArn"])
            raw["start_execution"] = start_response

            final_response = self._wait_for_execution(
                client=client,
                execution_arn=execution_arn,
                timeout_seconds=spec.timeout_seconds,
            )
            raw["describe_execution"] = final_response
            return ExecutionResult(
                status=str(final_response["status"]),
                backend=self.name,
                execution_arn=execution_arn,
                output_json=self._parse_json_output(_optional_str(final_response.get("output"))),
                error=_optional_str(final_response.get("error")),
                cause=_optional_str(final_response.get("cause")),
                next_state=None,
                raw=raw,
            )
        except ExecutionTimeoutError:
            if execution_arn is not None:
                stop_response = _stop_execution_best_effort(
                    client=client, execution_arn=execution_arn
                )
                if stop_response is not None:
                    raw["stop_execution"] = stop_response
            raise
        except (BotoCoreError, ClientError) as exc:
            action = "run an aws execution"
            raise self._backend_error(action, exc) from exc
        finally:
            if state_machine_arn is not None:
                with suppress(BotoCoreError, ClientError):
                    client.delete_state_machine(stateMachineArn=state_machine_arn)

    def test_state(self, spec: StateTestSpec) -> ExecutionResult:
        del spec
        msg = "The aws backend does not support sfn_test_state. Use the teststate backend."
        raise ConfigurationError(msg)

    def _wait_for_execution(
        self,
        *,
        client: StepFunctionsClientProtocol,
        execution_arn: str,
        timeout_seconds: int | None,
    ) -> dict[str, Any]:
        deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
        while True:
            response = client.describe_execution(executionArn=execution_arn)
            status = str(response.get("status", "UNKNOWN"))
            if status in _TERMINAL_STATUSES:
                return dict(response)
            if deadline is not None and time.monotonic() >= deadline:
                msg = (
                    f"Execution {execution_arn!r} did not finish within {timeout_seconds} seconds."
                )
                raise ExecutionTimeoutError(msg)
            time.sleep(_POLL_INTERVAL_SECONDS)


def _validate_run_spec(spec: ExecutionSpec) -> None:
    if spec.config.role_arn is None:
        msg = "The aws backend requires --sfn-role-arn or sfn_role_arn."
        raise ConfigurationError(msg)
    if spec.scenario.case is not None:
        msg = "The aws backend does not support Scenario.case. Use the local backend."
        raise ConfigurationError(msg)
    if spec.config.mock_config is not None:
        msg = "The aws backend does not support sfn_mock_config. Use the local backend."
        raise ConfigurationError(msg)
    if spec.config.local_endpoint != DEFAULT_LOCAL_ENDPOINT:
        msg = "The aws backend does not support --sfn-local-endpoint. Use the local backend."
        raise ConfigurationError(msg)


def _ephemeral_state_machine_name(base_name: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    prefix_length = _MAX_STATE_MACHINE_NAME_LENGTH - len(suffix) - 1
    prefix = base_name[:prefix_length].rstrip("-")
    if not prefix:
        prefix = "pytest-stepfunctions"
    return f"{prefix}-{suffix}"


def _stop_execution_best_effort(
    *,
    client: StepFunctionsClientProtocol,
    execution_arn: str,
) -> dict[str, Any] | None:
    with suppress(BotoCoreError, ClientError):
        response = client.stop_execution(
            executionArn=execution_arn,
            error=_TIMEOUT_STOP_ERROR,
            cause=_TIMEOUT_STOP_CAUSE,
        )
        return dict(response)
    return None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
