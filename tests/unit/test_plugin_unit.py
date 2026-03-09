from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, cast

import pytest
from _pytest.outcomes import Failed

import pytest_stepfunctions.plugin as plugin

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

    def getgroup(self, name: str) -> _FakeOptionGroup:
        self.group_name = name
        return self.group


class _FakeConfig:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def addinivalue_line(self, name: str, value: str) -> None:
        self.calls.append((name, value))


def test_pytest_addoption_registers_expected_cli_options() -> None:
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
    backend_option = dict(parser.group.options)["--sfn-backend"]
    assert backend_option["choices"] == ("auto", "local", "teststate", "aws")


def test_pytest_configure_registers_marker() -> None:
    config = _FakeConfig()

    plugin.pytest_configure(cast("pytest.Config", config))

    assert config.calls == [("markers", plugin._MARKER_DESCRIPTION)]


def test_not_implemented_backend_fails_without_pytrace() -> None:
    backend = plugin._not_implemented_backend("sfn_run")

    with pytest.raises(Failed, match="sfn_run is scaffolded but not implemented yet"):
        backend("ignored", definition={})


def test_plugin_module_can_be_reloaded() -> None:
    reloaded_module = importlib.reload(plugin)

    assert reloaded_module is plugin


def _fixture_factory(fixture: object) -> Callable[[], plugin.BackendCallable]:
    return cast("Callable[[], plugin.BackendCallable]", fixture.__wrapped__)  # type: ignore[attr-defined]


def test_fixture_wrappers_return_stub_callables() -> None:
    fixtures: list[tuple[str, Callable[[], plugin.BackendCallable]]] = [
        ("sfn_run", _fixture_factory(plugin.sfn_run)),
        ("sfn_test_state", _fixture_factory(plugin.sfn_test_state)),
    ]

    for fixture_name, factory in fixtures:
        backend = factory()
        with pytest.raises(Failed, match=fixture_name):
            backend()
