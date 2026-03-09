"""Public data models for pytest-stepfunctions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
            raise AssertionError(f"Expected execution status {expected!r}, got {self.status!r}.")

    def assert_succeeded(self) -> None:
        self.assert_status("SUCCEEDED")

    def assert_failed(self, error: str | None = None) -> None:
        if self.status != "FAILED":
            raise AssertionError(f"Expected execution to fail, got status {self.status!r}.")
        if error is not None and self.error != error:
            raise AssertionError(f"Expected error {error!r}, got {self.error!r}.")
