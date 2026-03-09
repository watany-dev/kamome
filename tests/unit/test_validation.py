from __future__ import annotations

import importlib

import pytest

import pytest_stepfunctions.exceptions as exceptions_module
import pytest_stepfunctions.validation as validation_module
from pytest_stepfunctions.validation import (
    ensure_validation_passed,
    validation_result_from_response,
)


def test_validation_module_can_be_reloaded() -> None:
    assert importlib.reload(validation_module) is validation_module


def test_validation_result_from_response_normalizes_diagnostics() -> None:
    result = validation_result_from_response(
        {
            "result": "FAIL",
            "diagnostics": [
                {
                    "severity": "ERROR",
                    "code": "ASL1001",
                    "message": "bad definition",
                    "location": {"line": 1, "column": 2},
                }
            ],
            "truncated": True,
        }
    )

    assert result.result == "FAIL"
    assert result.truncated is True
    assert result.diagnostics[0].location == '{"column": 2, "line": 1}'


def test_ensure_validation_passed_raises_actionable_error() -> None:
    result = validation_result_from_response(
        {
            "result": "FAIL",
            "diagnostics": [{"severity": "ERROR", "code": "ASL1001", "message": "bad definition"}],
        }
    )

    with pytest.raises(exceptions_module.ValidationError, match="validation failed"):
        ensure_validation_passed(result, source_label="workflow.asl.json")


def test_ensure_validation_passed_accepts_ok_result() -> None:
    result = validation_result_from_response({"result": "OK", "diagnostics": []})

    ensure_validation_passed(result, source_label="workflow.asl.json")


def test_validation_result_from_response_handles_non_mapping_diagnostic() -> None:
    result = validation_result_from_response({"result": "FAIL", "diagnostics": ["bad"]})

    assert result.diagnostics[0].message == "bad"


def test_ensure_validation_passed_handles_missing_diagnostics() -> None:
    result = validation_result_from_response({"result": "FAIL", "diagnostics": []})

    with pytest.raises(exceptions_module.ValidationError, match="No diagnostics"):
        ensure_validation_passed(result, source_label="workflow.asl.json")
