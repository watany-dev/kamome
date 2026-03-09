from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol, cast

import pytest

from pytest_stepfunctions import ExecutionResult, Scenario

TUTORIAL_ROOT = Path(__file__).resolve().parents[2] / "tutorials" / "order_status"
WORKFLOW_PATH = TUTORIAL_ROOT / "workflows" / "order_status.asl.json"
_RUN_LOCAL_INTEGRATION = os.environ.get("PYTEST_STEPFUNCTIONS_RUN_LOCAL_INTEGRATION") == "1"

pytestmark = [
    pytest.mark.skipif(
        not _RUN_LOCAL_INTEGRATION,
        reason=(
            "Set PYTEST_STEPFUNCTIONS_RUN_LOCAL_INTEGRATION=1 to run "
            "Step Functions Local integration tests."
        ),
    ),
    pytest.mark.sfn(definition=WORKFLOW_PATH, name="OrderStatusIntegration"),
]


class RunFixture(Protocol):
    def __call__(self, scenario: Scenario, **kwargs: object) -> ExecutionResult: ...


def _load_input(name: str) -> dict[str, Any]:
    path = TUTORIAL_ROOT / "inputs" / f"{name}.json"
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    ("scenario", "expected_output", "expected_error"),
    [
        (
            Scenario(id="paid", input=_load_input("paid")),
            {"decision": "complete", "orderId": "order-100", "status": "PAID"},
            None,
        ),
        (
            Scenario(id="pending", input=_load_input("pending")),
            None,
            "Order.NotPaid",
        ),
    ],
    ids=("paid", "pending"),
)
def test_local_backend_executes_tutorial_workflow(
    sfn_run: RunFixture,
    scenario: Scenario,
    expected_output: dict[str, Any] | None,
    expected_error: str | None,
) -> None:
    result = sfn_run(scenario)

    assert result.backend == "local"
    assert result.execution_arn is not None
    if expected_error is None:
        result.assert_succeeded()
        assert result.output_json == expected_output
        return

    result.assert_failed(expected_error)
    assert result.cause == "Order status was not PAID."
