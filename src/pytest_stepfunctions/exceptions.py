"""Custom exceptions for pytest-stepfunctions."""

from __future__ import annotations


class PytestStepFunctionsError(Exception):
    """Base exception for runtime failures."""


class ConfigurationError(PytestStepFunctionsError):
    """Raised when plugin or fixture configuration is invalid."""


class BackendResolutionError(ConfigurationError):
    """Raised when backend selection cannot be resolved."""


class DefinitionLoadError(ConfigurationError):
    """Raised when an ASL definition cannot be loaded or parsed."""


class ValidationError(PytestStepFunctionsError):
    """Raised when Step Functions definition validation fails."""


class BackendError(PytestStepFunctionsError):
    """Raised when a backend API call fails."""


class BackendNotImplementedError(BackendError):
    """Raised when a backend exists only as a stub."""


class ExecutionTimeoutError(BackendError):
    """Raised when an execution does not finish before the timeout."""


class MockCaseNotFoundError(ConfigurationError):
    """Raised when a configured Step Functions Local mock case is missing."""
