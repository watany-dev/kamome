from __future__ import annotations

import importlib
from dataclasses import FrozenInstanceError

import pytest

import pytest_stepfunctions.model as model


def test_model_module_can_be_reloaded() -> None:
    reloaded_module = importlib.reload(model)

    assert reloaded_module is model


def test_scenario_preserves_optional_fields() -> None:
    scenario = model.Scenario(
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


def test_scenario_is_frozen() -> None:
    scenario = model.Scenario(id="happy-path", input={"orderId": "o-1"})

    with pytest.raises(FrozenInstanceError):
        scenario.id = "other-path"  # type: ignore[misc]


def test_execution_result_assert_succeeded() -> None:
    result = model.ExecutionResult(
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
    result = model.ExecutionResult(
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
    result = model.ExecutionResult(
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


def test_execution_result_assert_failed_requires_failed_status() -> None:
    result = model.ExecutionResult(
        status="SUCCEEDED",
        backend="local",
        execution_arn=None,
        output_json={"status": "ok"},
        error=None,
        cause=None,
        next_state=None,
        raw={},
    )

    with pytest.raises(AssertionError, match="Expected execution to fail"):
        result.assert_failed()


def test_execution_result_assert_failed_reports_error_mismatch() -> None:
    result = model.ExecutionResult(
        status="FAILED",
        backend="local",
        execution_arn=None,
        output_json=None,
        error="Order.Timeout",
        cause=None,
        next_state="Reject",
        raw={},
    )

    with pytest.raises(AssertionError, match=r"Expected error 'Order\.NotPaid'"):
        result.assert_failed("Order.NotPaid")
