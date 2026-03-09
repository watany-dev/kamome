from __future__ import annotations

import pytest

from pytest_stepfunctions import ExecutionResult, Scenario


def test_scenario_preserves_optional_fields() -> None:
    scenario = Scenario(
        id="happy-path",
        input={"orderId": "o-1"},
        case="HappyPath",
        name="exec-1",
        timeout=30,
    )

    assert scenario.id == "happy-path"
    assert scenario.input == {"orderId": "o-1"}
    assert scenario.case == "HappyPath"
    assert scenario.name == "exec-1"
    assert scenario.timeout == 30


def test_execution_result_assert_succeeded() -> None:
    result = ExecutionResult(
        status="SUCCEEDED",
        backend="local",
        execution_arn="arn:aws:states:example",
        output_json={"status": "ok"},
        error=None,
        cause=None,
        next_state=None,
        raw={},
    )

    result.assert_succeeded()


def test_execution_result_assert_failed_with_expected_error() -> None:
    result = ExecutionResult(
        status="FAILED",
        backend="teststate",
        execution_arn=None,
        output_json=None,
        error="Order.NotPaid",
        cause="choice failed",
        next_state="Reject",
        raw={},
    )

    result.assert_failed("Order.NotPaid")


def test_execution_result_assert_status_reports_mismatch() -> None:
    result = ExecutionResult(
        status="FAILED",
        backend="local",
        execution_arn=None,
        output_json=None,
        error="Oops",
        cause=None,
        next_state=None,
        raw={},
    )

    with pytest.raises(AssertionError, match="Expected execution status 'SUCCEEDED'"):
        result.assert_status("SUCCEEDED")
