from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import pytest

if TYPE_CHECKING:
    from pytest_stepfunctions import ExecutionResult

TUTORIAL_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = TUTORIAL_ROOT / "workflows" / "order_status.asl.json"


class TestStateFixture(Protocol):
    def __call__(
        self,
        *,
        definition: object | None = None,
        state_name: str,
        input: dict[str, Any],  # noqa: A002
        **kwargs: object,
    ) -> ExecutionResult: ...


def _load_input(name: str) -> dict[str, Any]:
    path = TUTORIAL_ROOT / "inputs" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("input_name", "expected_next_state"),
    [("paid", "Complete"), ("pending", "Reject")],
    ids=("paid", "pending"),
)
def test_check_status_state(
    sfn_test_state: TestStateFixture,
    input_name: str,
    expected_next_state: str,
) -> None:
    result = sfn_test_state(
        definition=WORKFLOW_PATH,
        state_name="CheckStatus",
        input=_load_input(input_name),
    )

    result.assert_succeeded()
    assert result.backend == "teststate"
    assert result.next_state == expected_next_state
