"""Definition validation helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Normalized validation diagnostic."""

    severity: str
    code: str
    message: str
    location: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Normalized validation response."""

    result: str
    diagnostics: tuple[Diagnostic, ...]
    truncated: bool = False


def validation_result_from_response(response: Mapping[str, Any]) -> ValidationResult:
    """Normalize a boto3 validation response."""

    diagnostics = tuple(_diagnostic_from_item(item) for item in response.get("diagnostics", []))
    result = str(response.get("result", "UNKNOWN"))
    truncated = bool(response.get("truncated", False))
    return ValidationResult(result=result, diagnostics=diagnostics, truncated=truncated)


def ensure_validation_passed(result: ValidationResult, *, source_label: str) -> None:
    """Raise an actionable error if validation did not succeed."""

    if result.result == "OK":
        return

    diagnostic_lines = []
    for diagnostic in result.diagnostics:
        location = f" ({diagnostic.location})" if diagnostic.location else ""
        diagnostic_lines.append(
            f"[{diagnostic.severity}] {diagnostic.code}{location}: {diagnostic.message}"
        )
    rendered_diagnostics = "\n".join(diagnostic_lines) if diagnostic_lines else "No diagnostics."
    msg = f"Step Functions definition validation failed for {source_label}.\n{rendered_diagnostics}"
    raise ValidationError(msg)


def _diagnostic_from_item(item: object) -> Diagnostic:
    if not isinstance(item, Mapping):
        return Diagnostic(severity="UNKNOWN", code="UNKNOWN", message=str(item))

    severity = str(item.get("severity", "UNKNOWN"))
    code = str(item.get("code", "UNKNOWN"))
    message = str(item.get("message", ""))
    location_value = item.get("location")
    if location_value is None:
        location = None
    elif isinstance(location_value, str):
        location = location_value
    else:
        location = json.dumps(location_value, sort_keys=True)
    return Diagnostic(severity=severity, code=code, message=message, location=location)
