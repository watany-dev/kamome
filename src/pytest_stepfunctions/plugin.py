"""Pytest plugin entry point for pytest-stepfunctions."""

from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn

import pytest

BackendCallable = Callable[..., NoReturn]

_MARKER_DESCRIPTION = (
    "sfn(definition, name=None, backend=None, timeout=None): Step Functions test metadata"
)
_UNIMPLEMENTED_MESSAGE = (
    "{fixture_name} is scaffolded but not implemented yet. "
    "This repository currently ships the packaging and plugin skeleton only."
)


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("pytest-stepfunctions")
    group.addoption(
        "--sfn-backend",
        action="store",
        choices=("auto", "local", "teststate", "aws"),
        default=None,
        help="Select the Step Functions backend.",
    )
    group.addoption(
        "--sfn-region",
        action="store",
        default=None,
        help="AWS region for Step Functions API calls.",
    )
    group.addoption(
        "--sfn-local-endpoint",
        action="store",
        default=None,
        help="Override the Step Functions Local endpoint URL.",
    )
    group.addoption(
        "--sfn-role-arn",
        action="store",
        default=None,
        help="Role ARN for state machine creation on AWS backends.",
    )
    group.addoption(
        "--sfn-definition-root",
        action="store",
        default=None,
        help="Base directory for resolving ASL definition files.",
    )
    group.addoption(
        "--sfn-mock-config",
        action="store",
        default=None,
        help="Path to the Step Functions Local mock config file.",
    )
    group.addoption(
        "--sfn-validate",
        action="store_true",
        default=False,
        help="Validate definitions before execution when supported.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", _MARKER_DESCRIPTION)


def _not_implemented_backend(fixture_name: str) -> BackendCallable:
    def _runner(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        pytest.fail(_UNIMPLEMENTED_MESSAGE.format(fixture_name=fixture_name), pytrace=False)

    return _runner


@pytest.fixture
def sfn_run() -> BackendCallable:
    return _not_implemented_backend("sfn_run")


@pytest.fixture
def sfn_test_state() -> BackendCallable:
    return _not_implemented_backend("sfn_test_state")
