from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pytest_stepfunctions.definition import load_definition

TUTORIAL_ROOT = Path("tutorials/order_status")
WORKFLOW_PATH = TUTORIAL_ROOT / "workflows" / "order_status.asl.json"


def _load_input(name: str) -> dict[str, Any]:
    path = TUTORIAL_ROOT / "inputs" / f"{name}.json"
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def test_tutorial_workflow_definition_is_loadable() -> None:
    normalized = load_definition(WORKFLOW_PATH)

    assert normalized.source_label == str(WORKFLOW_PATH)
    assert normalized.document["StartAt"] == "CheckStatus"
    assert normalized.document["States"]["Reject"]["Error"] == "Order.NotPaid"


def test_tutorial_input_documents_are_json_objects() -> None:
    assert _load_input("paid") == {"orderId": "order-100", "status": "PAID"}
    assert _load_input("pending") == {"orderId": "order-200", "status": "PENDING"}
