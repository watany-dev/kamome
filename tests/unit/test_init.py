from __future__ import annotations

import importlib

import pytest

import pytest_stepfunctions
from pytest_stepfunctions import model as model_module


def test_package_exports_public_models() -> None:
    assert pytest_stepfunctions.__all__ == ["ExecutionResult", "Scenario"]
    assert pytest_stepfunctions.ExecutionResult is model_module.ExecutionResult
    assert pytest_stepfunctions.Scenario is model_module.Scenario


def test_package_registers_assert_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[str] = []

    def fake_register_assert_rewrite(module_name: str) -> None:
        recorded.append(module_name)

    monkeypatch.setattr(pytest, "register_assert_rewrite", fake_register_assert_rewrite)

    importlib.reload(pytest_stepfunctions)

    assert recorded == ["pytest_stepfunctions.helpers.assertions"]
