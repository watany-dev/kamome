"""AWS TestState backend."""

from __future__ import annotations

from botocore.exceptions import BotoCoreError, ClientError

from ..exceptions import ConfigurationError
from ..model import ExecutionResult, ExecutionSpec, StateTestSpec
from .base import Backend


class TestStateBackend(Backend):
    """Backend for AWS TestState API calls."""

    name = "teststate"

    def run(self, spec: ExecutionSpec) -> ExecutionResult:
        del spec
        msg = "The teststate backend only supports sfn_test_state."
        raise ConfigurationError(msg)

    def test_state(self, spec: StateTestSpec) -> ExecutionResult:
        if spec.config.role_arn is None:
            msg = "The teststate backend requires --sfn-role-arn or sfn_role_arn."
            raise ConfigurationError(msg)

        client = self._service_client()
        try:
            response = client.test_state(
                definition=self._json_dump(spec.definition),
                roleArn=spec.config.role_arn,
                input=self._json_dump(spec.input),
                inspectionLevel="INFO",
                stateName=spec.state_name,
            )
        except (BotoCoreError, ClientError) as exc:
            action = "call TestState"
            raise self._backend_error(action, exc) from exc

        return ExecutionResult(
            status=str(response["status"]),
            backend=self.name,
            execution_arn=None,
            output_json=self._parse_json_output(_optional_str(response.get("output"))),
            error=_optional_str(response.get("error")),
            cause=_optional_str(response.get("cause")),
            next_state=_optional_str(response.get("nextState")),
            raw=dict(response),
        )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
