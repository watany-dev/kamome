from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from botocore.exceptions import ClientError

from pytest_stepfunctions.backends import create_backend, resolve_backend_name
from pytest_stepfunctions.backends.aws import AwsBackend
from pytest_stepfunctions.backends.base import Backend
from pytest_stepfunctions.backends.local import LocalBackend, _assert_mock_case_exists
from pytest_stepfunctions.backends.teststate import TestStateBackend as _TestStateBackend
from pytest_stepfunctions.config import ResolvedConfig
from pytest_stepfunctions.exceptions import (
    BackendError,
    BackendNotImplementedError,
    ConfigurationError,
    ExecutionTimeoutError,
    MockCaseNotFoundError,
)
from pytest_stepfunctions.model import ExecutionResult, ExecutionSpec, Scenario, StateTestSpec

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_stepfunctions.backends.base import StepFunctionsClientProtocol


class _FakeLocalClient:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.describe_calls = 0

    def create_state_machine(self, **kwargs: object) -> dict[str, object]:
        self.created = kwargs
        return {"stateMachineArn": "arn:aws:states:local:stateMachine:OrderFlow"}

    def start_execution(self, **kwargs: object) -> dict[str, object]:
        self.started = kwargs
        return {"executionArn": "arn:aws:states:local:execution:OrderFlow:exec-1"}

    def describe_execution(self, **kwargs: object) -> dict[str, object]:
        self.describe_calls += 1
        self.described = kwargs
        return {
            "status": "SUCCEEDED",
            "output": '{"status": "paid"}',
        }

    def delete_state_machine(self, **kwargs: object) -> None:
        self.deleted.append(str(kwargs["stateMachineArn"]))


class _FakeTestStateClient:
    def test_state(self, **kwargs: object) -> dict[str, object]:
        self.called = kwargs
        return {
            "status": "SUCCEEDED",
            "output": '{"status": "paid"}',
            "nextState": "Complete",
        }


class _DummyBackend(Backend):
    name = "dummy"

    def run(self, spec: ExecutionSpec) -> ExecutionResult:
        del spec
        return ExecutionResult(
            status="SUCCEEDED",
            backend="dummy",
            execution_arn=None,
            output_json=None,
            error=None,
            cause=None,
            next_state=None,
            raw={},
        )

    def test_state(self, spec: StateTestSpec) -> ExecutionResult:
        del spec
        return ExecutionResult(
            status="SUCCEEDED",
            backend="dummy",
            execution_arn=None,
            output_json=None,
            error=None,
            cause=None,
            next_state=None,
            raw={},
        )


def _config(
    *,
    backend: str = "auto",
    region: str = "us-east-1",
    local_endpoint: str = "http://127.0.0.1:8083",
    role_arn: str | None = None,
    definition_root: Path | None = None,
    mock_config: Path | None = None,
    validate: bool = False,
) -> ResolvedConfig:
    return ResolvedConfig(
        backend=backend,
        region=region,
        local_endpoint=local_endpoint,
        role_arn=role_arn,
        definition_root=definition_root,
        mock_config=mock_config,
        validate=validate,
    )


def test_resolve_backend_name_auto_rules() -> None:
    assert resolve_backend_name("auto", state_name=None) == "local"
    assert resolve_backend_name("auto", state_name="CheckStatus") == "teststate"


def test_resolve_backend_name_rejects_invalid_backend() -> None:
    with pytest.raises(ConfigurationError, match="Unsupported Step Functions backend"):
        resolve_backend_name("invalid", state_name=None)


def test_create_backend_returns_expected_backend_types() -> None:
    config = _config()

    assert isinstance(create_backend("local", config=config, state_name=None), LocalBackend)
    assert isinstance(
        create_backend("teststate", config=config, state_name="Check"), _TestStateBackend
    )
    assert isinstance(create_backend("aws", config=config, state_name=None), AwsBackend)


def test_backend_validate_and_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _DummyBackend(_config())

    class _ValidatingClient:
        def validate_state_machine_definition(self, **kwargs: object) -> dict[str, object]:
            self.kwargs = kwargs
            return {"result": "OK", "diagnostics": []}

    client = _ValidatingClient()

    def fake_service_client(**_kwargs: object) -> _ValidatingClient:
        return client

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    result = backend.validate({"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}})

    assert result.result == "OK"
    assert client.kwargs["severity"] == "ERROR"
    assert backend._json_dump({"hello": "world"}) == '{"hello": "world"}'
    assert backend._parse_json_output('{"hello": "world"}') == {"hello": "world"}
    assert backend._parse_json_output(None) is None
    assert "dummy backend failed" in str(backend._backend_error("run", RuntimeError("boom")))


def test_backend_validate_wraps_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _DummyBackend(_config())

    class _FailingClient:
        def validate_state_machine_definition(self, **kwargs: object) -> dict[str, object]:
            del kwargs
            raise ClientError({"Error": {"Code": "Boom", "Message": "bad"}}, "Validate")

    def fake_service_client(**_kwargs: object) -> _FailingClient:
        return _FailingClient()

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    with pytest.raises(BackendError, match="validate definition"):
        backend.validate({})


def test_service_client_uses_dummy_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}
    backend = _DummyBackend(_config())

    def fake_boto3_client(service_name: str, **kwargs: object) -> object:
        recorded["service_name"] = service_name
        recorded.update(kwargs)
        return object()

    monkeypatch.setattr("pytest_stepfunctions.backends.base.boto3.client", fake_boto3_client)

    backend._service_client(endpoint_url="http://local", use_dummy_credentials=True)

    assert recorded["service_name"] == "stepfunctions"
    assert recorded["region_name"] == "us-east-1"
    assert recorded["endpoint_url"] == "http://local"
    assert recorded["aws_access_key_id"] == "dummy"


def test_local_backend_run_translates_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeLocalClient()
    backend = LocalBackend(_config(local_endpoint="http://local"))

    def fake_service_client(**_kwargs: object) -> _FakeLocalClient:
        return client

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    result = backend.run(
        ExecutionSpec(
            definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
            definition_source="<inline>",
            state_machine_name="OrderFlow",
            execution_name="exec-1",
            scenario=Scenario(id="happy", input={"orderId": "o-1"}, case="HappyPath"),
            timeout_seconds=5,
            config=_config(local_endpoint="http://local"),
        )
    )

    assert result.status == "SUCCEEDED"
    assert result.output_json == {"status": "paid"}
    assert (
        client.started["stateMachineArn"] == "arn:aws:states:local:stateMachine:OrderFlow#HappyPath"
    )
    assert client.deleted == ["arn:aws:states:local:stateMachine:OrderFlow"]


def test_local_backend_wait_for_execution_times_out() -> None:
    backend = LocalBackend(_config())

    class _SlowClient:
        def describe_execution(self, **_kwargs: object) -> dict[str, object]:
            return {"status": "RUNNING"}

    with pytest.raises(ExecutionTimeoutError, match="did not finish"):
        backend._wait_for_execution(
            client=cast("StepFunctionsClientProtocol", _SlowClient()),
            execution_arn="arn",
            timeout_seconds=0,
        )


def test_assert_mock_case_exists_validates_structure(tmp_path: Path) -> None:
    path = tmp_path / "MockConfigFile.json"
    path.write_text(
        '{"StateMachines": {"OrderFlow": {"TestCases": {"HappyPath": {}}}}}',
        encoding="utf-8",
    )

    _assert_mock_case_exists(
        mock_config_path=path,
        state_machine_name="OrderFlow",
        case_name="HappyPath",
    )


def test_assert_mock_case_exists_raises_for_missing_case(tmp_path: Path) -> None:
    path = tmp_path / "MockConfigFile.json"
    path.write_text('{"StateMachines": {"OrderFlow": {"TestCases": {}}}}', encoding="utf-8")

    with pytest.raises(MockCaseNotFoundError, match="HappyPath"):
        _assert_mock_case_exists(
            mock_config_path=path,
            state_machine_name="OrderFlow",
            case_name="HappyPath",
        )


def test_teststate_backend_requires_role_arn() -> None:
    backend = _TestStateBackend(_config())

    with pytest.raises(ConfigurationError, match="requires --sfn-role-arn"):
        backend.test_state(
            StateTestSpec(
                definition={"StartAt": "Check", "States": {"Check": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_name="Check",
                input={},
                timeout_seconds=None,
                config=_config(),
            )
        )


def test_teststate_backend_maps_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeTestStateClient()
    backend = _TestStateBackend(_config(role_arn="arn:aws:iam::1:role/test"))

    def fake_service_client(**_kwargs: object) -> _FakeTestStateClient:
        return client

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    result = backend.test_state(
        StateTestSpec(
            definition={"StartAt": "Check", "States": {"Check": {"Type": "Succeed"}}},
            definition_source="<inline>",
            state_name="Check",
            input={"status": "PAID"},
            timeout_seconds=None,
            config=_config(role_arn="arn:aws:iam::1:role/test"),
        )
    )

    assert result.status == "SUCCEEDED"
    assert result.output_json == {"status": "paid"}
    assert result.next_state == "Complete"


def test_aws_backend_is_stub() -> None:
    backend = AwsBackend(_config(backend="aws"))

    with pytest.raises(BackendNotImplementedError, match="not implemented"):
        backend.run(
            ExecutionSpec(
                definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_machine_name="OrderFlow",
                execution_name="exec-1",
                scenario=Scenario(id="happy", input={}),
                timeout_seconds=None,
                config=_config(backend="aws"),
            )
        )


def test_aws_backend_test_state_is_stub() -> None:
    backend = AwsBackend(_config(backend="aws"))

    with pytest.raises(BackendNotImplementedError, match="not implemented"):
        backend.test_state(
            StateTestSpec(
                definition={"StartAt": "Check", "States": {"Check": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_name="Check",
                input={},
                timeout_seconds=None,
                config=_config(backend="aws"),
            )
        )


def test_local_backend_test_state_is_rejected() -> None:
    backend = LocalBackend(_config())

    with pytest.raises(ConfigurationError, match="does not support sfn_test_state"):
        backend.test_state(
            StateTestSpec(
                definition={"StartAt": "Check", "States": {"Check": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_name="Check",
                input={},
                timeout_seconds=None,
                config=_config(),
            )
        )


def test_local_backend_wraps_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = LocalBackend(_config())

    class _FailingClient:
        def create_state_machine(self, **kwargs: object) -> dict[str, object]:
            del kwargs
            raise ClientError({"Error": {"Code": "Boom", "Message": "bad"}}, "CreateStateMachine")

    def fake_service_client(**_kwargs: object) -> _FailingClient:
        return _FailingClient()

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    with pytest.raises(BackendError, match="local backend failed"):
        backend.run(
            ExecutionSpec(
                definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_machine_name="OrderFlow",
                execution_name="exec-1",
                scenario=Scenario(id="happy", input={}),
                timeout_seconds=None,
                config=_config(),
            )
        )


def test_assert_mock_case_exists_rejects_invalid_shapes(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Invalid JSON"):
        _assert_mock_case_exists(
            mock_config_path=bad_json,
            state_machine_name="OrderFlow",
            case_name="HappyPath",
        )

    missing_state_machines = tmp_path / "missing.json"
    missing_state_machines.write_text("{}", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="must contain 'StateMachines'"):
        _assert_mock_case_exists(
            mock_config_path=missing_state_machines,
            state_machine_name="OrderFlow",
            case_name="HappyPath",
        )


def test_teststate_backend_run_is_rejected() -> None:
    backend = _TestStateBackend(_config(role_arn="arn:aws:iam::1:role/test"))

    with pytest.raises(ConfigurationError, match="only supports sfn_test_state"):
        backend.run(
            ExecutionSpec(
                definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_machine_name="OrderFlow",
                execution_name="exec-1",
                scenario=Scenario(id="happy", input={}),
                timeout_seconds=None,
                config=_config(role_arn="arn:aws:iam::1:role/test"),
            )
        )


def test_teststate_backend_wraps_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _TestStateBackend(_config(role_arn="arn:aws:iam::1:role/test"))

    class _FailingClient:
        def test_state(self, **kwargs: object) -> dict[str, object]:
            del kwargs
            raise ClientError({"Error": {"Code": "Boom", "Message": "bad"}}, "TestState")

    def fake_service_client(**_kwargs: object) -> _FailingClient:
        return _FailingClient()

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    with pytest.raises(BackendError, match="call TestState"):
        backend.test_state(
            StateTestSpec(
                definition={"StartAt": "Check", "States": {"Check": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_name="Check",
                input={},
                timeout_seconds=None,
                config=_config(role_arn="arn:aws:iam::1:role/test"),
            )
        )
