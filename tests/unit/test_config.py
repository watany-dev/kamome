from __future__ import annotations

import importlib
from pathlib import Path

import pytest_stepfunctions.config as config_module
from pytest_stepfunctions.config import DEFAULT_LOCAL_ENDPOINT, DEFAULT_REGION, resolve_config


class _FakeConfig:
    def __init__(self) -> None:
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
            "sfn_region": DEFAULT_REGION,
            "sfn_local_endpoint": DEFAULT_LOCAL_ENDPOINT,
            "sfn_role_arn": "",
            "sfn_definition_root": "",
            "sfn_mock_config": "",
            "sfn_validate": False,
        }

    def getoption(self, name: str) -> object:
        return self.options[name]

    def getini(self, name: str) -> object:
        return self.ini[name]


class _FakeParser:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def addini(self, name: str, ini_help: str, **kwargs: object) -> None:
        self.calls.append((name, {"help": ini_help, **kwargs}))


def test_config_module_can_be_reloaded() -> None:
    assert importlib.reload(config_module) is config_module


def test_resolve_config_uses_expected_precedence() -> None:
    config = _FakeConfig()
    config.options["sfn_region"] = "us-west-2"
    config.ini["sfn_definition_root"] = "tests/workflows"

    resolved = resolve_config(
        config,  # type: ignore[arg-type]
        marker_backend="local",
        override_backend="teststate",
        override_mock_config="tests/mocks.json",
        override_validate=True,
    )

    assert resolved.backend == "teststate"
    assert resolved.region == "us-west-2"
    assert resolved.definition_root == Path("tests/workflows")
    assert resolved.mock_config == Path("tests/mocks.json")
    assert resolved.validate is True


def test_resolve_config_falls_back_to_ini_defaults() -> None:
    resolved = resolve_config(_FakeConfig())  # type: ignore[arg-type]

    assert resolved.backend == "auto"
    assert resolved.region == DEFAULT_REGION
    assert resolved.local_endpoint == DEFAULT_LOCAL_ENDPOINT
    assert resolved.role_arn is None
    assert resolved.definition_root is None
    assert resolved.mock_config is None
    assert resolved.validate is False


def test_resolve_config_uses_cli_when_fixture_and_marker_do_not_override() -> None:
    config = _FakeConfig()
    config.options["sfn_backend"] = "local"
    config.options["sfn_definition_root"] = "definitions"

    resolved = resolve_config(config)  # type: ignore[arg-type]

    assert resolved.backend == "local"
    assert resolved.definition_root == Path("definitions")


def test_register_ini_options_registers_all_supported_keys() -> None:
    parser = _FakeParser()

    config_module.register_ini_options(parser)  # type: ignore[arg-type]

    names = [name for name, _kwargs in parser.calls]
    assert names == [
        "sfn_backend",
        "sfn_region",
        "sfn_local_endpoint",
        "sfn_role_arn",
        "sfn_definition_root",
        "sfn_mock_config",
        "sfn_validate",
    ]


def test_resolve_config_accepts_path_overrides() -> None:
    resolved = resolve_config(
        _FakeConfig(),  # type: ignore[arg-type]
        override_definition_root=Path("defs"),
        override_mock_config=Path("mock.json"),
    )

    assert resolved.definition_root == Path("defs")
    assert resolved.mock_config == Path("mock.json")
