from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from botocore.exceptions import ClientError

from pytest_stepfunctions.backends import create_backend, resolve_backend_name
from pytest_stepfunctions.backends.aws import AwsBackend
from pytest_stepfunctions.backends.base import Backend
from pytest_stepfunctions.backends.local import (
    LocalBackend,
    _assert_mock_case_exists,
    _failure_details_from_history,
    _is_retryable_state_machine_error,
    _load_mock_config_document,
)
from pytest_stepfunctions.backends.teststate import TestStateBackend as _TestStateBackend
from pytest_stepfunctions.config import ResolvedConfig
from pytest_stepfunctions.exceptions import (
    BackendError,
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
        self.create_calls = 0
        self.start_calls = 0

    def create_state_machine(self, **kwargs: object) -> dict[str, object]:
        self.create_calls += 1
        self.created = kwargs
        return {"stateMachineArn": "arn:aws:states:local:stateMachine:OrderFlow"}

    def start_execution(self, **kwargs: object) -> dict[str, object]:
        self.start_calls += 1
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

    def get_execution_history(self, **kwargs: object) -> dict[str, object]:
        self.history_kwargs = kwargs
        return {"events": []}


class _RetryingLocalClient(_FakeLocalClient):
    def __init__(self, *, failures_before_success: int = 1) -> None:
        super().__init__()
        self.failures_before_success = failures_before_success

    def start_execution(self, **kwargs: object) -> dict[str, object]:
        self.start_calls += 1
        self.started = kwargs
        if self.start_calls <= self.failures_before_success:
            raise ClientError(
                {"Error": {"Code": "StateMachineDeleting", "Message": "state machine is deleting"}},
                "StartExecution",
            )
        return {"executionArn": "arn:aws:states:local:execution:OrderFlow:exec-1"}


class _FakeTestStateClient:
    def test_state(self, **kwargs: object) -> dict[str, object]:
        self.called = kwargs
        return {
            "status": "SUCCEEDED",
            "output": '{"status": "paid"}',
            "nextState": "Complete",
        }


class _FakeAwsClient:
    def __init__(self, *, statuses: list[dict[str, object]] | None = None) -> None:
        self.deleted: list[str] = []
        self.describe_calls = 0
        self.statuses = statuses or [{"status": "SUCCEEDED", "output": '{"status": "paid"}'}]
        self.stop_calls: list[dict[str, object]] = []

    def create_state_machine(self, **kwargs: object) -> dict[str, object]:
        self.created = kwargs
        return {"stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:OrderFlow"}

    def start_execution(self, **kwargs: object) -> dict[str, object]:
        self.started = kwargs
        return {"executionArn": "arn:aws:states:us-east-1:123456789012:execution:OrderFlow:exec-1"}

    def describe_execution(self, **kwargs: object) -> dict[str, object]:
        self.describe_calls += 1
        self.described = kwargs
        index = min(self.describe_calls - 1, len(self.statuses) - 1)
        return self.statuses[index]

    def stop_execution(self, **kwargs: object) -> dict[str, object]:
        self.stop_calls.append(kwargs)
        return {"stopDate": "2026-03-09T00:00:00Z"}

    def delete_state_machine(self, **kwargs: object) -> None:
        self.deleted.append(str(kwargs["stateMachineArn"]))


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


def test_local_backend_reads_failure_details_from_execution_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailedLocalClient(_FakeLocalClient):
        def describe_execution(self, **kwargs: object) -> dict[str, object]:
            self.describe_calls += 1
            self.described = kwargs
            return {"status": "FAILED"}

        def get_execution_history(self, **kwargs: object) -> dict[str, object]:
            self.history_kwargs = kwargs
            return {
                "events": [
                    {
                        "executionFailedEventDetails": {
                            "error": "Order.NotPaid",
                            "cause": "Order status was not PAID.",
                        }
                    }
                ]
            }

    client = _FailedLocalClient()
    backend = LocalBackend(_config(local_endpoint="http://local"))

    def fake_service_client(**_kwargs: object) -> _FailedLocalClient:
        return client

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    result = backend.run(
        ExecutionSpec(
            definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
            definition_source="<inline>",
            state_machine_name="OrderFlow",
            execution_name="exec-1",
            scenario=Scenario(id="pending", input={"orderId": "o-1"}),
            timeout_seconds=5,
            config=_config(local_endpoint="http://local"),
        )
    )

    assert result.status == "FAILED"
    assert result.error == "Order.NotPaid"
    assert result.cause == "Order status was not PAID."
    assert client.history_kwargs == {
        "executionArn": "arn:aws:states:local:execution:OrderFlow:exec-1"
    }


def test_local_backend_retries_state_machine_deleting_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _RetryingLocalClient(failures_before_success=3)
    backend = LocalBackend(_config(local_endpoint="http://local"))

    def fake_service_client(**_kwargs: object) -> _FakeLocalClient:
        return client

    monkeypatch.setattr(backend, "_service_client", fake_service_client)
    monkeypatch.setattr("pytest_stepfunctions.backends.local.time.sleep", lambda _seconds: None)

    result = backend.run(
        ExecutionSpec(
            definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
            definition_source="<inline>",
            state_machine_name="OrderFlow",
            execution_name="exec-1",
            scenario=Scenario(id="happy", input={"orderId": "o-1"}),
            timeout_seconds=5,
            config=_config(local_endpoint="http://local"),
        )
    )

    assert result.status == "SUCCEEDED"
    assert client.create_calls == 4
    assert client.start_calls == 4
    assert client.deleted == ["arn:aws:states:local:stateMachine:OrderFlow"] * 4


def test_local_backend_stops_retrying_state_machine_deleting_errors_after_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _RetryingLocalClient(failures_before_success=999)
    backend = LocalBackend(_config(local_endpoint="http://local"))
    monotonic_values = iter((0.0, 1.0, 2.0, 3.0, 4.0, 5.1))

    def fake_service_client(**_kwargs: object) -> _FakeLocalClient:
        return client

    monkeypatch.setattr(backend, "_service_client", fake_service_client)
    monkeypatch.setattr("pytest_stepfunctions.backends.local.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        "pytest_stepfunctions.backends.local.time.monotonic",
        lambda: next(monotonic_values),
    )

    with pytest.raises(BackendError, match="run a local execution"):
        backend.run(
            ExecutionSpec(
                definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_machine_name="OrderFlow",
                execution_name="exec-1",
                scenario=Scenario(id="happy", input={"orderId": "o-1"}),
                timeout_seconds=5,
                config=_config(local_endpoint="http://local"),
            )
        )

    assert client.create_calls == 5
    assert client.start_calls == 5
    assert client.deleted == ["arn:aws:states:local:stateMachine:OrderFlow"] * 5


def test_local_backend_retries_state_machine_already_exists_on_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _CreateRetryClient(_FakeLocalClient):
        def create_state_machine(self, **kwargs: object) -> dict[str, object]:
            self.create_calls += 1
            self.created = kwargs
            if self.create_calls == 1:
                raise ClientError(
                    {"Error": {"Code": "StateMachineAlreadyExists", "Message": "already exists"}},
                    "CreateStateMachine",
                )
            return {"stateMachineArn": "arn:aws:states:local:stateMachine:OrderFlow"}

    client = _CreateRetryClient()
    backend = LocalBackend(_config(local_endpoint="http://local"))

    def fake_service_client(**_kwargs: object) -> _CreateRetryClient:
        return client

    monkeypatch.setattr(backend, "_service_client", fake_service_client)
    monkeypatch.setattr("pytest_stepfunctions.backends.local.time.sleep", lambda _seconds: None)

    result = backend.run(
        ExecutionSpec(
            definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
            definition_source="<inline>",
            state_machine_name="OrderFlow",
            execution_name="exec-1",
            scenario=Scenario(id="happy", input={"orderId": "o-1"}),
            timeout_seconds=5,
            config=_config(local_endpoint="http://local"),
        )
    )

    assert result.status == "SUCCEEDED"
    assert client.create_calls == 2
    assert client.deleted == ["arn:aws:states:local:stateMachine:OrderFlow"]


def test_local_backend_wraps_non_retryable_client_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailingClient(_FakeLocalClient):
        def create_state_machine(self, **kwargs: object) -> dict[str, object]:
            del kwargs
            raise ClientError({"Error": {"Code": "Boom", "Message": "bad"}}, "CreateStateMachine")

    backend = LocalBackend(_config(local_endpoint="http://local"))

    def fake_service_client(**_kwargs: object) -> _FailingClient:
        return _FailingClient()

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    with pytest.raises(BackendError, match="run a local execution"):
        backend.run(
            ExecutionSpec(
                definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_machine_name="OrderFlow",
                execution_name="exec-1",
                scenario=Scenario(id="happy", input={"orderId": "o-1"}),
                timeout_seconds=5,
                config=_config(local_endpoint="http://local"),
            )
        )


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


def test_local_backend_wait_for_execution_polls_until_terminal_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = LocalBackend(_config())

    class _PollingClient:
        def __init__(self) -> None:
            self.calls = 0

        def describe_execution(self, **_kwargs: object) -> dict[str, object]:
            self.calls += 1
            if self.calls == 1:
                return {"status": "RUNNING"}
            return {"status": "SUCCEEDED", "output": '{"status": "paid"}'}

    client = _PollingClient()
    monkeypatch.setattr("pytest_stepfunctions.backends.local.time.sleep", lambda _seconds: None)

    result = backend._wait_for_execution(
        client=cast("StepFunctionsClientProtocol", client),
        execution_arn="arn",
        timeout_seconds=1,
    )

    assert result["status"] == "SUCCEEDED"
    assert client.calls == 2


def test_failure_details_from_history_handles_missing_or_malformed_events() -> None:
    class _HistoryClient:
        def __init__(self, response: dict[str, object]) -> None:
            self.response = response

        def get_execution_history(self, **_kwargs: object) -> dict[str, object]:
            return self.response

    assert (
        _failure_details_from_history(
            client=cast("StepFunctionsClientProtocol", _HistoryClient({"events": "bad"})),
            execution_arn="arn",
        )
        == {}
    )
    assert (
        _failure_details_from_history(
            client=cast(
                "StepFunctionsClientProtocol",
                _HistoryClient(
                    {
                        "events": [
                            "bad",
                            {"type": "ExecutionStarted"},
                            {"executionFailedEventDetails": {"error": 1, "cause": None}},
                        ]
                    }
                ),
            ),
            execution_arn="arn",
        )
        == {}
    )


def test_is_retryable_state_machine_error_recognizes_supported_codes() -> None:
    assert _is_retryable_state_machine_error(
        ClientError(
            {"Error": {"Code": "StateMachineDeleting", "Message": "deleting"}},
            "StartExecution",
        )
    )
    assert not _is_retryable_state_machine_error(
        ClientError({"Error": {"Code": "Boom", "Message": "bad"}}, "StartExecution")
    )


def test_assert_mock_case_exists_validates_structure(tmp_path: Path) -> None:
    path = tmp_path / "MockConfigFile.json"
    path.write_text(
        '{"StateMachines": {"OrderFlow": {"TestCases": {"HappyPath": {}}}}}',
        encoding="utf-8",
    )

    document = _load_mock_config_document(path)
    _assert_mock_case_exists(
        mock_document=document,
        mock_config_path=path,
        state_machine_name="OrderFlow",
        case_name="HappyPath",
    )


def test_assert_mock_case_exists_raises_for_missing_case(tmp_path: Path) -> None:
    path = tmp_path / "MockConfigFile.json"
    path.write_text('{"StateMachines": {"OrderFlow": {"TestCases": {}}}}', encoding="utf-8")

    document = _load_mock_config_document(path)
    with pytest.raises(MockCaseNotFoundError, match="HappyPath"):
        _assert_mock_case_exists(
            mock_document=document,
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


def test_aws_backend_run_translates_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeAwsClient()
    backend = AwsBackend(_config(backend="aws", role_arn="arn:aws:iam::1:role/test"))

    def fake_service_client(**_kwargs: object) -> _FakeAwsClient:
        return client

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    result = backend.run(
        ExecutionSpec(
            definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
            definition_source="<inline>",
            state_machine_name="OrderFlow",
            execution_name="exec-1",
            scenario=Scenario(id="happy", input={"orderId": "o-1"}),
            timeout_seconds=5,
            config=_config(backend="aws", role_arn="arn:aws:iam::1:role/test"),
        )
    )

    assert result.status == "SUCCEEDED"
    assert result.output_json == {"status": "paid"}
    assert result.backend == "aws"
    assert str(client.created["roleArn"]) == "arn:aws:iam::1:role/test"
    assert str(client.started["stateMachineArn"]).startswith(
        "arn:aws:states:us-east-1:123456789012:stateMachine:OrderFlow"
    )
    assert client.deleted == ["arn:aws:states:us-east-1:123456789012:stateMachine:OrderFlow"]


def test_aws_backend_maps_failed_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeAwsClient(
        statuses=[
            {
                "status": "FAILED",
                "error": "Order.NotPaid",
                "cause": "Order status was not PAID.",
            }
        ]
    )
    backend = AwsBackend(_config(backend="aws", role_arn="arn:aws:iam::1:role/test"))

    def fake_service_client(**_kwargs: object) -> _FakeAwsClient:
        return client

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    result = backend.run(
        ExecutionSpec(
            definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
            definition_source="<inline>",
            state_machine_name="OrderFlow",
            execution_name="exec-1",
            scenario=Scenario(id="pending", input={"orderId": "o-1"}),
            timeout_seconds=5,
            config=_config(backend="aws", role_arn="arn:aws:iam::1:role/test"),
        )
    )

    assert result.status == "FAILED"
    assert result.error == "Order.NotPaid"
    assert result.cause == "Order status was not PAID."


def test_aws_backend_timeout_stops_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeAwsClient(statuses=[{"status": "RUNNING"}])
    backend = AwsBackend(_config(backend="aws", role_arn="arn:aws:iam::1:role/test"))

    def fake_service_client(**_kwargs: object) -> _FakeAwsClient:
        return client

    monkeypatch.setattr(backend, "_service_client", fake_service_client)
    monkeypatch.setattr("pytest_stepfunctions.backends.aws.time.monotonic", lambda: 0.0)

    with pytest.raises(ExecutionTimeoutError, match="did not finish"):
        backend.run(
            ExecutionSpec(
                definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_machine_name="OrderFlow",
                execution_name="exec-1",
                scenario=Scenario(id="timeout", input={"orderId": "o-1"}),
                timeout_seconds=0,
                config=_config(backend="aws", role_arn="arn:aws:iam::1:role/test"),
            )
        )

    assert client.stop_calls == [
        {
            "executionArn": "arn:aws:states:us-east-1:123456789012:execution:OrderFlow:exec-1",
            "error": "PytestStepFunctions.Timeout",
            "cause": "Execution exceeded the configured pytest-stepfunctions timeout.",
        }
    ]
    assert client.deleted == ["arn:aws:states:us-east-1:123456789012:stateMachine:OrderFlow"]


def test_aws_backend_requires_role_arn() -> None:
    backend = AwsBackend(_config(backend="aws"))

    with pytest.raises(ConfigurationError, match="requires --sfn-role-arn"):
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


def test_aws_backend_rejects_local_only_options(tmp_path: Path) -> None:
    backend = AwsBackend(_config(backend="aws", role_arn="arn:aws:iam::1:role/test"))

    with pytest.raises(ConfigurationError, match=r"Scenario\.case"):
        backend.run(
            ExecutionSpec(
                definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_machine_name="OrderFlow",
                execution_name="exec-1",
                scenario=Scenario(id="happy", input={}, case="HappyPath"),
                timeout_seconds=None,
                config=_config(backend="aws", role_arn="arn:aws:iam::1:role/test"),
            )
        )

    with pytest.raises(ConfigurationError, match="sfn_mock_config"):
        backend.run(
            ExecutionSpec(
                definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_machine_name="OrderFlow",
                execution_name="exec-1",
                scenario=Scenario(id="happy", input={}),
                timeout_seconds=None,
                config=_config(
                    backend="aws",
                    role_arn="arn:aws:iam::1:role/test",
                    mock_config=tmp_path / "mock.json",
                ),
            )
        )

    with pytest.raises(ConfigurationError, match="sfn-local-endpoint"):
        backend.run(
            ExecutionSpec(
                definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_machine_name="OrderFlow",
                execution_name="exec-1",
                scenario=Scenario(id="happy", input={}),
                timeout_seconds=None,
                config=_config(
                    backend="aws",
                    role_arn="arn:aws:iam::1:role/test",
                    local_endpoint="http://custom-local",
                ),
            )
        )


def test_aws_backend_test_state_is_rejected() -> None:
    backend = AwsBackend(_config(backend="aws", role_arn="arn:aws:iam::1:role/test"))

    with pytest.raises(ConfigurationError, match="does not support sfn_test_state"):
        backend.test_state(
            StateTestSpec(
                definition={"StartAt": "Check", "States": {"Check": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_name="Check",
                input={},
                timeout_seconds=None,
                config=_config(backend="aws", role_arn="arn:aws:iam::1:role/test"),
            )
        )


def test_aws_backend_wraps_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AwsBackend(_config(backend="aws", role_arn="arn:aws:iam::1:role/test"))

    class _FailingClient:
        def create_state_machine(self, **kwargs: object) -> dict[str, object]:
            del kwargs
            raise ClientError({"Error": {"Code": "Boom", "Message": "bad"}}, "CreateStateMachine")

        def delete_state_machine(self, **kwargs: object) -> None:
            del kwargs

    def fake_service_client(**_kwargs: object) -> _FailingClient:
        return _FailingClient()

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    with pytest.raises(BackendError, match="run an aws execution"):
        backend.run(
            ExecutionSpec(
                definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_machine_name="OrderFlow",
                execution_name="exec-1",
                scenario=Scenario(id="happy", input={}),
                timeout_seconds=None,
                config=_config(backend="aws", role_arn="arn:aws:iam::1:role/test"),
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
        _load_mock_config_document(bad_json)

    missing_state_machines = tmp_path / "missing.json"
    missing_state_machines.write_text("{}", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="must contain 'StateMachines'"):
        _load_mock_config_document(missing_state_machines)

    invalid_state_machine = tmp_path / "invalid-state-machine.json"
    invalid_state_machine.write_text('{"StateMachines": {"OrderFlow": []}}', encoding="utf-8")
    with pytest.raises(ConfigurationError, match="invalid state machine entry"):
        _load_mock_config_document(invalid_state_machine)

    invalid_test_cases = tmp_path / "invalid-test-cases.json"
    invalid_test_cases.write_text(
        '{"StateMachines": {"OrderFlow": {"TestCases": []}}}',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="must define 'TestCases'"):
        _load_mock_config_document(invalid_test_cases)

    invalid_case_entry = tmp_path / "invalid-case-entry.json"
    invalid_case_entry.write_text(
        '{"StateMachines": {"OrderFlow": {"TestCases": {"HappyPath": []}}}}',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="invalid test case entry"):
        _load_mock_config_document(invalid_case_entry)


def test_local_backend_validates_mock_config_without_case(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mock_config = tmp_path / "MockConfigFile.json"
    mock_config.write_text('{"StateMachines": {"OrderFlow": []}}', encoding="utf-8")
    backend = LocalBackend(_config(mock_config=mock_config))

    class _UnexpectedClient(_FakeLocalClient):
        def create_state_machine(self, **kwargs: object) -> dict[str, object]:
            del kwargs
            msg = "client should not be called when mock config is invalid"
            raise AssertionError(msg)

    def fake_service_client(**_kwargs: object) -> _UnexpectedClient:
        return _UnexpectedClient()

    monkeypatch.setattr(backend, "_service_client", fake_service_client)

    with pytest.raises(ConfigurationError, match="invalid state machine entry"):
        backend.run(
            ExecutionSpec(
                definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                definition_source="<inline>",
                state_machine_name="OrderFlow",
                execution_name="exec-1",
                scenario=Scenario(id="happy", input={}),
                timeout_seconds=None,
                config=_config(mock_config=mock_config),
            )
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
