from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest
from _pytest.outcomes import Failed

import pytest_stepfunctions.plugin as plugin
from pytest_stepfunctions import Scenario
from pytest_stepfunctions.markers import MARKER_DESCRIPTION
from pytest_stepfunctions.model import ExecutionResult, ExecutionSpec, StateTestSpec
from pytest_stepfunctions.validation import ValidationResult

if TYPE_CHECKING:
    from collections.abc import Callable


class _FakeOptionGroup:
    def __init__(self) -> None:
        self.options: list[tuple[str, dict[str, object]]] = []

    def addoption(self, name: str, **kwargs: object) -> None:
        self.options.append((name, kwargs))


class _FakeParser:
    def __init__(self) -> None:
        self.group_name: str | None = None
        self.group = _FakeOptionGroup()
        self.ini_options: list[tuple[str, dict[str, object]]] = []

    def getgroup(self, name: str) -> _FakeOptionGroup:
        self.group_name = name
        return self.group

    def addini(self, name: str, ini_help: str, **kwargs: object) -> None:
        self.ini_options.append((name, {"help": ini_help, **kwargs}))


class _FakeConfig:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.options: dict[str, object] = {
            "sfn_backend": None,
            "sfn_region": None,
            "sfn_local_endpoint": None,
            "sfn_role_arn": None,
            "sfn_definition_root": None,
            "sfn_mock_config": None,
            "sfn_validate": False,
        }
        self.ini: dict[str, object] = {
            "sfn_backend": "auto",
            "sfn_region": "us-east-1",
            "sfn_local_endpoint": "http://127.0.0.1:8083",
            "sfn_role_arn": "",
            "sfn_definition_root": "",
            "sfn_mock_config": "",
            "sfn_validate": False,
        }

    def addinivalue_line(self, name: str, value: str) -> None:
        self.calls.append((name, value))

    def getoption(self, name: str) -> object:
        return self.options[name]

    def getini(self, name: str) -> object:
        return self.ini[name]


@dataclass
class _FakeMarker:
    args: tuple[object, ...] = ()
    kwargs: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.kwargs is None:
            self.kwargs = {}


class _FakeNode:
    def __init__(self, *, name: str = "test_case", marker: _FakeMarker | None = None) -> None:
        self.name = name
        self.nodeid = f"tests/test_sample.py::{name}"
        self._marker = marker

    def get_closest_marker(self, name: str) -> _FakeMarker | None:
        assert name == "sfn"
        return self._marker


class _FakeRequest:
    def __init__(self, *, config: _FakeConfig, node: _FakeNode) -> None:
        self.config = config
        self.node = node


class _FakeBackend:
    def __init__(self) -> None:
        self.name = "local"
        self.validated: list[dict[str, object]] = []
        self.run_specs: list[ExecutionSpec] = []
        self.state_specs: list[StateTestSpec] = []

    def validate(self, definition: dict[str, object]) -> ValidationResult:
        self.validated.append(definition)
        return ValidationResult(result="OK", diagnostics=(), truncated=False)

    def run(self, spec: ExecutionSpec) -> ExecutionResult:
        self.run_specs.append(spec)
        return ExecutionResult(
            status="SUCCEEDED",
            backend="local",
            execution_arn="arn:aws:states:example:execution",
            output_json={"status": "ok"},
            error=None,
            cause=None,
            next_state=None,
            raw={},
        )

    def test_state(self, spec: StateTestSpec) -> ExecutionResult:
        self.state_specs.append(spec)
        return ExecutionResult(
            status="SUCCEEDED",
            backend="teststate",
            execution_arn=None,
            output_json={"status": "ok"},
            error=None,
            cause=None,
            next_state="NextState",
            raw={},
        )


def _fixture_factory(fixture: object) -> Callable[..., object]:
    return cast("Callable[..., object]", fixture.__wrapped__)  # type: ignore[attr-defined]


def test_pytest_addoption_registers_expected_cli_and_ini_options() -> None:
    parser = _FakeParser()

    plugin.pytest_addoption(cast("pytest.Parser", parser))

    assert parser.group_name == "pytest-stepfunctions"
    option_names = [name for name, _kwargs in parser.group.options]
    assert option_names == [
        "--sfn-backend",
        "--sfn-region",
        "--sfn-local-endpoint",
        "--sfn-role-arn",
        "--sfn-definition-root",
        "--sfn-mock-config",
        "--sfn-validate",
    ]
    ini_names = [name for name, _kwargs in parser.ini_options]
    assert ini_names == [
        "sfn_backend",
        "sfn_region",
        "sfn_local_endpoint",
        "sfn_role_arn",
        "sfn_definition_root",
        "sfn_mock_config",
        "sfn_validate",
    ]


def test_pytest_configure_registers_marker() -> None:
    config = _FakeConfig()

    plugin.pytest_configure(cast("pytest.Config", config))

    assert config.calls == [("markers", MARKER_DESCRIPTION)]


def test_plugin_module_can_be_reloaded() -> None:
    reloaded_module = importlib.reload(plugin)

    assert reloaded_module is plugin


def test_sfn_run_fixture_executes_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _FakeConfig()
    config.options["sfn_region"] = "us-west-2"
    request = _FakeRequest(
        config=config,
        node=_FakeNode(
            marker=_FakeMarker(
                kwargs={
                    "definition": {"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
                    "name": "Order Flow",
                    "timeout": 12,
                }
            )
        ),
    )
    backend = _FakeBackend()

    def fake_create_backend(*_args: object, **_kwargs: object) -> _FakeBackend:
        return backend

    monkeypatch.setattr(plugin, "create_backend", fake_create_backend)

    fixture = _fixture_factory(plugin.sfn_run)
    runner = cast("plugin.RunCallable", fixture(request))
    result = runner(
        Scenario(id="happy", input={"orderId": "o-1"}, name="exec name"),
        validate=True,
        backend="auto",
    )

    result.assert_succeeded()
    assert backend.validated == [{"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}]
    spec = backend.run_specs[0]
    assert spec.state_machine_name == "Order-Flow"
    assert spec.execution_name == "exec-name"
    assert spec.timeout_seconds == 12
    assert spec.config.region == "us-west-2"
    assert spec.config.backend == "local"


def test_sfn_test_state_fixture_executes_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _FakeConfig()
    request = _FakeRequest(
        config=config,
        node=_FakeNode(
            marker=_FakeMarker(
                kwargs={
                    "definition": {"StartAt": "Check", "States": {"Check": {"Type": "Succeed"}}},
                    "backend": "auto",
                }
            )
        ),
    )
    backend = _FakeBackend()
    backend.name = "teststate"

    def fake_create_backend(*_args: object, **_kwargs: object) -> _FakeBackend:
        return backend

    monkeypatch.setattr(plugin, "create_backend", fake_create_backend)

    fixture = _fixture_factory(plugin.sfn_test_state)
    runner = cast("plugin.StateCallable", fixture(request))
    result = runner(state_name="Check", input={"status": "PAID"}, role_arn="arn:aws:iam::1:role/t")

    assert result.next_state == "NextState"
    spec = backend.state_specs[0]
    assert spec.state_name == "Check"
    assert spec.input == {"status": "PAID"}
    assert spec.config.backend == "teststate"


def test_sfn_run_fixture_requires_definition() -> None:
    request = _FakeRequest(config=_FakeConfig(), node=_FakeNode())
    fixture = _fixture_factory(plugin.sfn_run)
    runner = cast("plugin.RunCallable", fixture(request))

    with pytest.raises(Failed, match="definition is required"):
        runner(Scenario(id="missing", input={}))


def test_sfn_run_fixture_requires_scenario_instance() -> None:
    request = _FakeRequest(
        config=_FakeConfig(),
        node=_FakeNode(
            marker=_FakeMarker(kwargs={"definition": {"StartAt": "Done", "States": {}}})
        ),
    )
    fixture = _fixture_factory(plugin.sfn_run)
    runner = cast("plugin.RunCallable", fixture(request))

    with pytest.raises(Failed, match="Scenario instance"):
        runner({"id": "wrong"})


def test_sfn_test_state_fixture_requires_state_name() -> None:
    request = _FakeRequest(
        config=_FakeConfig(),
        node=_FakeNode(
            marker=_FakeMarker(kwargs={"definition": {"StartAt": "Done", "States": {}}})
        ),
    )
    fixture = _fixture_factory(plugin.sfn_test_state)
    runner = cast("plugin.StateCallable", fixture(request))

    with pytest.raises(Failed, match="state_name"):
        runner(state_name="", input={})


def test_sanitize_name_truncates_and_hashes() -> None:
    sanitized = plugin._sanitize_name("x" * 100, max_length=20)

    assert len(sanitized) == 20
    assert sanitized.startswith("xxxxxxxxxxx-")


def test_definition_based_name_uses_path_stem() -> None:
    request = _FakeRequest(config=_FakeConfig(), node=_FakeNode(name="test_from_marker"))
    normalized = type(
        "Normalized",
        (),
        {"source_label": "/workspaces/kamome/order_flow.asl.json"},
    )()

    assert (
        plugin._definition_based_name(
            normalized,
            cast("pytest.FixtureRequest", request),
        )
        == "order_flow"
    )
