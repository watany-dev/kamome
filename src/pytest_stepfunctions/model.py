"""Public data models for pytest-stepfunctions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import ResolvedConfig


class ExecutionAssertionError(AssertionError):
    """Base assertion error for execution result helpers."""


class ExecutionStatusAssertionError(ExecutionAssertionError):
    """Raised when an execution status differs from the expected value."""

    def __init__(self, *, expected: str, actual: str) -> None:
        super().__init__(f"Expected execution status {expected!r}, got {actual!r}.")


class ExecutionFailedAssertionError(ExecutionAssertionError):
    """Raised when a failed execution assertion sees another status."""

    def __init__(self, *, actual: str) -> None:
        super().__init__(f"Expected execution to fail, got status {actual!r}.")


class ExecutionErrorMismatchAssertionError(ExecutionAssertionError):
    """Raised when a failed execution has an unexpected error code."""

    def __init__(self, *, expected: str, actual: str | None) -> None:
        super().__init__(f"Expected error {expected!r}, got {actual!r}.")


@dataclass(frozen=True, slots=True)
class Scenario:
    """Scenario input for state machine executions."""

    id: str
    input: dict[str, Any]
    case: str | None = None
    name: str | None = None
    timeout: int | None = None


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Backend-agnostic execution result."""

    status: str
    backend: str
    execution_arn: str | None
    output_json: Any | None
    error: str | None
    cause: str | None
    next_state: str | None
    raw: dict[str, Any]

    def assert_status(self, expected: str) -> None:
        if self.status != expected:
            raise ExecutionStatusAssertionError(expected=expected, actual=self.status)

    def assert_succeeded(self) -> None:
        self.assert_status("SUCCEEDED")

    def assert_failed(self, error: str | None = None) -> None:
        if self.status != "FAILED":
            raise ExecutionFailedAssertionError(actual=self.status)
        if error is not None and self.error != error:
            raise ExecutionErrorMismatchAssertionError(expected=error, actual=self.error)


@dataclass(frozen=True, slots=True)
class ExecutionSpec:
    """Internal spec for full workflow execution."""

    definition: dict[str, Any]
    definition_source: str
    state_machine_name: str
    execution_name: str
    scenario: Scenario
    timeout_seconds: int | None
    config: ResolvedConfig


@dataclass(frozen=True, slots=True)
class StateTestSpec:
    """Internal spec for a single-state test."""

    definition: dict[str, Any]
    definition_source: str
    state_name: str
    input: dict[str, Any]
    timeout_seconds: int | None
    config: ResolvedConfig
