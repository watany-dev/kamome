"""Pytest plugin entry point for pytest-stepfunctions."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from .backends import create_backend
from .config import register_ini_options, resolve_config
from .definition import NormalizedDefinition, load_definition
from .exceptions import ConfigurationError, PytestStepFunctionsError
from .markers import MARKER_DESCRIPTION, MarkerSettings, extract_marker_settings
from .model import ExecutionResult, ExecutionSpec, Scenario, StateTestSpec
from .validation import ensure_validation_passed

if TYPE_CHECKING:
    from .backends.base import Backend

RunCallable = Callable[..., ExecutionResult]
StateCallable = Callable[..., ExecutionResult]


def pytest_addoption(parser: pytest.Parser) -> None:
    register_ini_options(parser)
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
    config.addinivalue_line("markers", MARKER_DESCRIPTION)


@pytest.fixture
def sfn_run(request: pytest.FixtureRequest) -> RunCallable:
    marker_settings = extract_marker_settings(request.node)

    def _runner(
        scenario: Scenario,
        *,
        definition: object | None = None,
        name: str | None = None,
        backend: str | None = None,
        timeout: int | None = None,
        validate: bool | None = None,
        region: str | None = None,
        local_endpoint: str | None = None,
        role_arn: str | None = None,
        definition_root: str | Path | None = None,
        mock_config: str | Path | None = None,
    ) -> ExecutionResult:
        try:
            _ensure_scenario(scenario)
            runtime_config = resolve_config(
                request.config,
                marker_backend=marker_settings.backend,
                override_backend=backend,
                override_region=region,
                override_local_endpoint=local_endpoint,
                override_role_arn=role_arn,
                override_definition_root=definition_root,
                override_mock_config=mock_config,
                override_validate=validate,
            )
            normalized_definition = load_definition(
                _require_definition(definition, marker_settings=marker_settings),
                definition_root=runtime_config.definition_root,
            )
            spec = ExecutionSpec(
                definition=normalized_definition.document,
                definition_source=normalized_definition.source_label,
                state_machine_name=_resolve_state_machine_name(
                    requested_name=name,
                    marker_name=marker_settings.name,
                    request=request,
                    normalized_definition=normalized_definition,
                ),
                execution_name=_resolve_execution_name(request=request, scenario=scenario),
                scenario=scenario,
                timeout_seconds=timeout if timeout is not None else marker_settings.timeout,
                config=runtime_config,
            )
            backend_impl = create_backend(
                runtime_config.backend,
                config=runtime_config,
                state_name=None,
            )
            resolved_spec = replace(spec, config=replace(runtime_config, backend=backend_impl.name))
            return _execute_run(backend_impl=backend_impl, spec=resolved_spec)
        except PytestStepFunctionsError as exc:
            pytest.fail(str(exc), pytrace=False)

    return _runner


@pytest.fixture
def sfn_test_state(request: pytest.FixtureRequest) -> StateCallable:
    marker_settings = extract_marker_settings(request.node)

    def _runner(
        *,
        definition: object | None = None,
        state_name: str,
        input: dict[str, Any],  # noqa: A002
        backend: str | None = None,
        timeout: int | None = None,
        validate: bool | None = None,
        region: str | None = None,
        local_endpoint: str | None = None,
        role_arn: str | None = None,
        definition_root: str | Path | None = None,
        mock_config: str | Path | None = None,
    ) -> ExecutionResult:
        try:
            _ensure_state_name(state_name)
            runtime_config = resolve_config(
                request.config,
                marker_backend=marker_settings.backend,
                override_backend=backend,
                override_region=region,
                override_local_endpoint=local_endpoint,
                override_role_arn=role_arn,
                override_definition_root=definition_root,
                override_mock_config=mock_config,
                override_validate=validate,
            )
            normalized_definition = load_definition(
                _require_definition(definition, marker_settings=marker_settings),
                definition_root=runtime_config.definition_root,
            )
            spec = StateTestSpec(
                definition=normalized_definition.document,
                definition_source=normalized_definition.source_label,
                state_name=state_name,
                input=input,
                timeout_seconds=timeout if timeout is not None else marker_settings.timeout,
                config=runtime_config,
            )
            backend_impl = create_backend(
                runtime_config.backend,
                config=runtime_config,
                state_name=state_name,
            )
            resolved_spec = replace(spec, config=replace(runtime_config, backend=backend_impl.name))
            return _execute_state_test(backend_impl=backend_impl, spec=resolved_spec)
        except PytestStepFunctionsError as exc:
            pytest.fail(str(exc), pytrace=False)

    return _runner


def _require_definition(
    override_definition: object | None,
    *,
    marker_settings: MarkerSettings,
) -> object:
    definition = (
        override_definition if override_definition is not None else marker_settings.definition
    )
    if definition is None:
        msg = "Step Functions definition is required via fixture argument or @pytest.mark.sfn."
        raise ConfigurationError(msg)
    return definition


def _ensure_scenario(scenario: object) -> None:
    if isinstance(scenario, Scenario):
        return
    required_attributes = ("id", "input", "case", "name", "timeout")
    if all(hasattr(scenario, attribute) for attribute in required_attributes):
        return
    msg = "sfn_run expects a pytest_stepfunctions.Scenario instance."
    raise ConfigurationError(msg)


def _ensure_state_name(state_name: object) -> None:
    if isinstance(state_name, str) and state_name.strip():
        return
    msg = "sfn_test_state requires a non-empty state_name string."
    raise ConfigurationError(msg)


def _maybe_validate(
    *, backend_impl: Backend, definition: dict[str, Any], definition_source: str, validate: bool
) -> None:
    if validate:
        ensure_validation_passed(
            backend_impl.validate(definition),
            source_label=definition_source,
        )


def _execute_run(*, backend_impl: Backend, spec: ExecutionSpec) -> ExecutionResult:
    _maybe_validate(
        backend_impl=backend_impl,
        definition=spec.definition,
        definition_source=spec.definition_source,
        validate=spec.config.validate,
    )
    return backend_impl.run(spec)


def _execute_state_test(*, backend_impl: Backend, spec: StateTestSpec) -> ExecutionResult:
    _maybe_validate(
        backend_impl=backend_impl,
        definition=spec.definition,
        definition_source=spec.definition_source,
        validate=spec.config.validate,
    )
    return backend_impl.test_state(spec)


def _resolve_state_machine_name(
    *,
    requested_name: str | None,
    marker_name: str | None,
    request: pytest.FixtureRequest,
    normalized_definition: NormalizedDefinition,
) -> str:
    base_name = (
        requested_name or marker_name or _definition_based_name(normalized_definition, request)
    )
    return _sanitize_name(base_name, max_length=80)


def _definition_based_name(
    normalized_definition: NormalizedDefinition,
    request: pytest.FixtureRequest,
) -> str:
    if normalized_definition.source_label.startswith("/"):
        return Path(normalized_definition.source_label).stem.replace(".asl", "")
    return str(request.node.name)


def _resolve_execution_name(*, request: pytest.FixtureRequest, scenario: Scenario) -> str:
    base_name = scenario.name or f"{request.node.name}-{scenario.id}"
    return _sanitize_name(base_name, max_length=80)


def _sanitize_name(value: str, *, max_length: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
    if not cleaned:
        cleaned = "pytest-stepfunctions"
    if len(cleaned) <= max_length:
        return cleaned
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:8]
    prefix = cleaned[: max_length - len(digest) - 1].rstrip("-")
    return f"{prefix}-{digest}"
