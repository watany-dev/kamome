from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import pytest

from pytest_stepfunctions import ExecutionResult, Scenario

TUTORIAL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = TUTORIAL_ROOT / "workflows" / "order_status.asl.json"

pytestmark = pytest.mark.sfn(definition=WORKFLOW_PATH, name="OrderStatusTutorial")


class RunFixture(Protocol):
    def __call__(self, scenario: Scenario, **kwargs: object) -> ExecutionResult: ...


def _load_input(name: str) -> dict[str, Any]:
    path = TUTORIAL_ROOT / "inputs" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


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
def test_order_status_workflow(
    sfn_run: RunFixture,
    scenario: Scenario,
    expected_output: dict[str, Any] | None,
    expected_error: str | None,
) -> None:
    result = sfn_run(scenario)

    assert result.backend == "local"
    if expected_error is None:
        result.assert_succeeded()
        assert result.output_json == expected_output
        return

    result.assert_failed(expected_error)
    assert result.cause == "Order status was not PAID."
