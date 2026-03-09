"""Step Functions Local backend."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from botocore.exceptions import BotoCoreError, ClientError

from ..exceptions import ConfigurationError, ExecutionTimeoutError, MockCaseNotFoundError
from ..model import ExecutionResult
from .base import Backend, StepFunctionsClientProtocol

if TYPE_CHECKING:
    from pathlib import Path

    from ..model import ExecutionSpec, StateTestSpec

_DEFAULT_LOCAL_ROLE_ARN = "arn:aws:iam::123456789012:role/pytest-stepfunctions-local"
_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"}
_RETRYABLE_STATE_MACHINE_ERROR_CODES = {"StateMachineAlreadyExists", "StateMachineDeleting"}
_STATE_MACHINE_RETRY_INITIAL_DELAY_SECONDS = 0.1
_STATE_MACHINE_RETRY_MAX_DELAY_SECONDS = 0.5
_STATE_MACHINE_RETRY_TIMEOUT_SECONDS = 5.0


class LocalBackend(Backend):
    """Backend for full workflow execution against Step Functions Local."""

    name = "local"

    def run(self, spec: ExecutionSpec) -> ExecutionResult:
        if spec.config.mock_config is not None:
            mock_document = _load_mock_config_document(spec.config.mock_config)
            if spec.scenario.case is not None:
                _assert_mock_case_exists(
                    mock_document=mock_document,
                    mock_config_path=spec.config.mock_config,
                    state_machine_name=spec.state_machine_name,
                    case_name=spec.scenario.case,
                )

        client = self._service_client(
            endpoint_url=spec.config.local_endpoint,
            use_dummy_credentials=True,
        )
        state_machine_arn: str | None = None
        retry_deadline = time.monotonic() + _STATE_MACHINE_RETRY_TIMEOUT_SECONDS
        retry_delay_seconds = _STATE_MACHINE_RETRY_INITIAL_DELAY_SECONDS

        try:
            while True:
                try:
                    create_response = client.create_state_machine(
                        name=spec.state_machine_name,
                        definition=self._json_dump(spec.definition),
                        roleArn=spec.config.role_arn or _DEFAULT_LOCAL_ROLE_ARN,
                        type="STANDARD",
                    )
                    state_machine_arn = str(create_response["stateMachineArn"])

                    start_response = client.start_execution(
                        stateMachineArn=_execution_target_arn(
                            state_machine_arn=state_machine_arn,
                            case_name=spec.scenario.case,
                        ),
                        name=spec.execution_name,
                        input=self._json_dump(spec.scenario.input),
                    )
                    execution_arn = str(start_response["executionArn"])
                    final_response = self._wait_for_execution(
                        client=client,
                        execution_arn=execution_arn,
                        timeout_seconds=spec.timeout_seconds,
                    )
                    if str(final_response.get("status")) == "FAILED":
                        final_response.update(
                            _failure_details_from_history(
                                client=client,
                                execution_arn=execution_arn,
                            )
                        )
                    return ExecutionResult(
                        status=str(final_response["status"]),
                        backend=self.name,
                        execution_arn=execution_arn,
                        output_json=self._parse_json_output(final_response.get("output")),
                        error=_optional_str(final_response.get("error")),
                        cause=_optional_str(final_response.get("cause")),
                        next_state=None,
                        raw={
                            "create_state_machine": create_response,
                            "start_execution": start_response,
                            "describe_execution": final_response,
                        },
                    )
                except ClientError as exc:
                    if _is_retryable_state_machine_error(exc) and time.monotonic() < retry_deadline:
                        if state_machine_arn is not None:
                            with suppress(BotoCoreError, ClientError):
                                client.delete_state_machine(stateMachineArn=state_machine_arn)
                            state_machine_arn = None
                        time.sleep(retry_delay_seconds)
                        retry_delay_seconds = min(
                            retry_delay_seconds * 2,
                            _STATE_MACHINE_RETRY_MAX_DELAY_SECONDS,
                        )
                        continue
                    action = "run a local execution"
                    raise self._backend_error(action, exc) from exc
                except BotoCoreError as exc:
                    action = "run a local execution"
                    raise self._backend_error(action, exc) from exc
        finally:
            if state_machine_arn is not None:
                with suppress(BotoCoreError, ClientError):
                    client.delete_state_machine(stateMachineArn=state_machine_arn)

    def test_state(self, spec: StateTestSpec) -> ExecutionResult:
        del spec
        msg = "The local backend does not support sfn_test_state. Use the teststate backend."
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
            time.sleep(0.05)


def _execution_target_arn(*, state_machine_arn: str, case_name: str | None) -> str:
    if case_name is None:
        return state_machine_arn
    return f"{state_machine_arn}#{case_name}"


def _failure_details_from_history(
    *,
    client: StepFunctionsClientProtocol,
    execution_arn: str,
) -> dict[str, str]:
    response = client.get_execution_history(executionArn=execution_arn)
    events = response.get("events")
    if not isinstance(events, list):
        return {}

    for event in reversed(events):
        if not isinstance(event, Mapping):
            continue
        details = event.get("executionFailedEventDetails")
        if not isinstance(details, Mapping):
            continue

        failure_details = {
            key: value
            for key, value in (
                ("error", _optional_str(details.get("error"))),
                ("cause", _optional_str(details.get("cause"))),
            )
            if value is not None
        }
        if failure_details:
            return failure_details
    return {}


def _is_retryable_state_machine_error(exc: ClientError) -> bool:
    error = exc.response.get("Error", {})
    code = error.get("Code")
    return isinstance(code, str) and code in _RETRYABLE_STATE_MACHINE_ERROR_CODES


def _load_mock_config_document(mock_config_path: Path) -> Mapping[str, Any]:
    try:
        contents = mock_config_path.read_text(encoding="utf-8")
        document = json.loads(contents)
    except OSError as exc:
        msg = f"Could not read Step Functions Local mock config {mock_config_path}: {exc}"
        raise ConfigurationError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in Step Functions Local mock config {mock_config_path}: {exc.msg}"
        raise ConfigurationError(msg) from exc

    if not isinstance(document, Mapping):
        msg = f"Step Functions Local mock config {mock_config_path} must be a JSON object."
        raise ConfigurationError(msg)

    state_machines = document.get("StateMachines")
    if not isinstance(state_machines, Mapping):
        msg = f"Step Functions Local mock config {mock_config_path} must contain 'StateMachines'."
        raise ConfigurationError(msg)

    for state_machine_key, state_machine_entry in state_machines.items():
        if not isinstance(state_machine_entry, Mapping):
            msg = (
                "Step Functions Local mock config "
                f"{mock_config_path} has invalid state machine entry {state_machine_key!r}."
            )
            raise ConfigurationError(msg)

        test_cases = state_machine_entry.get("TestCases")
        if not isinstance(test_cases, Mapping):
            msg = (
                "Step Functions Local mock config "
                f"{mock_config_path} must define 'TestCases' for state machine "
                f"{state_machine_key!r}."
            )
            raise ConfigurationError(msg)

        for case_key, case_entry in test_cases.items():
            if not isinstance(case_entry, Mapping):
                msg = (
                    "Step Functions Local mock config "
                    f"{mock_config_path} has invalid test case entry "
                    f"{state_machine_key!r}.{case_key!r}."
                )
                raise ConfigurationError(msg)

    return state_machines


def _assert_mock_case_exists(
    *,
    mock_document: Mapping[str, Any],
    mock_config_path: Path,
    state_machine_name: str,
    case_name: str,
) -> None:
    state_machine_entry = mock_document.get(state_machine_name)
    if state_machine_entry is None and len(mock_document) == 1:
        state_machine_entry = next(iter(mock_document.values()))
    if not isinstance(state_machine_entry, Mapping):
        msg = (
            f"Mock config {mock_config_path} does not contain state machine {state_machine_name!r}."
        )
        raise MockCaseNotFoundError(msg)

    test_cases = state_machine_entry.get("TestCases")
    if not isinstance(test_cases, Mapping) or case_name not in test_cases:
        msg = f"Mock config {mock_config_path} does not contain test case {case_name!r}."
        raise MockCaseNotFoundError(msg)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
