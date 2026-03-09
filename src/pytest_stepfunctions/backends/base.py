"""Backend base classes and shared helpers."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, cast

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..exceptions import BackendError
from ..validation import ValidationResult, validation_result_from_response

if TYPE_CHECKING:
    from ..config import ResolvedConfig
    from ..model import ExecutionResult, ExecutionSpec, StateTestSpec

_DUMMY_CREDENTIAL = "dummy"


class StepFunctionsClientProtocol(Protocol):
    """Subset of the boto3 Step Functions client used by this plugin."""

    def validate_state_machine_definition(self, **kwargs: object) -> dict[str, object]: ...

    def create_state_machine(self, **kwargs: object) -> dict[str, object]: ...

    def start_execution(self, **kwargs: object) -> dict[str, object]: ...

    def describe_execution(self, **kwargs: object) -> dict[str, object]: ...

    def delete_state_machine(self, **kwargs: object) -> object: ...

    def test_state(self, **kwargs: object) -> dict[str, object]: ...


class Backend(ABC):
    """Shared backend contract."""

    name: str

    def __init__(self, config: ResolvedConfig) -> None:
        self.config = config

    def validate(self, definition: dict[str, Any]) -> ValidationResult:
        """Validate a state machine definition using the AWS API."""

        try:
            response = self._service_client().validate_state_machine_definition(
                definition=self._json_dump(definition),
                severity="ERROR",
                type="STANDARD",
            )
        except (BotoCoreError, ClientError) as exc:
            action = "validate definition"
            raise self._backend_error(action, exc) from exc
        return validation_result_from_response(response)

    @abstractmethod
    def run(self, spec: ExecutionSpec) -> ExecutionResult:
        """Execute a full state machine."""

    @abstractmethod
    def test_state(self, spec: StateTestSpec) -> ExecutionResult:
        """Execute a single state using the backend."""

    def _service_client(
        self,
        *,
        endpoint_url: str | None = None,
        use_dummy_credentials: bool = False,
    ) -> StepFunctionsClientProtocol:
        kwargs: dict[str, object] = {"region_name": self.config.region}
        if endpoint_url is not None:
            kwargs["endpoint_url"] = endpoint_url
        if use_dummy_credentials:
            kwargs["aws_access_key_id"] = _DUMMY_CREDENTIAL
            kwargs["aws_secret_access_key"] = _DUMMY_CREDENTIAL
            kwargs["aws_session_token"] = _DUMMY_CREDENTIAL
        return cast("StepFunctionsClientProtocol", boto3.client("stepfunctions", **kwargs))

    def _json_dump(self, payload: object) -> str:
        return json.dumps(payload)

    def _parse_json_output(self, payload: str | None) -> object | None:
        if payload is None:
            return None
        return cast("object", json.loads(payload))

    def _backend_error(self, action: str, exc: Exception) -> BackendError:
        return BackendError(f"{self.name} backend failed to {action}: {exc}")
