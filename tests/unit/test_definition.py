from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pytest

import pytest_stepfunctions.definition as definition_module
from pytest_stepfunctions.definition import load_definition
from pytest_stepfunctions.exceptions import DefinitionLoadError

if TYPE_CHECKING:
    from pathlib import Path


def test_definition_module_can_be_reloaded() -> None:
    assert importlib.reload(definition_module) is definition_module


def test_load_definition_from_mapping() -> None:
    result = load_definition({"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}})

    assert result.document["StartAt"] == "Done"
    assert result.source_label == "<inline definition>"


def test_load_definition_from_json_string() -> None:
    result = load_definition('{"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}')

    assert result.document["States"]["Done"]["Type"] == "Succeed"
    assert result.source_label == "<inline JSON definition>"


def test_load_definition_from_relative_path(tmp_path: Path) -> None:
    definition_root = tmp_path / "definitions"
    definition_root.mkdir()
    path = definition_root / "workflow.asl.json"
    path.write_text(
        '{"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}', encoding="utf-8"
    )

    result = load_definition("workflow.asl.json", definition_root=definition_root)

    assert result.document["StartAt"] == "Done"
    assert result.source_label == str(path)


def test_load_definition_from_path_object(tmp_path: Path) -> None:
    path = tmp_path / "workflow.asl.json"
    path.write_text(
        '{"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}', encoding="utf-8"
    )

    result = load_definition(path)

    assert result.source_label == str(path)


def test_load_definition_rejects_invalid_json() -> None:
    with pytest.raises(DefinitionLoadError, match="Invalid JSON"):
        load_definition("{not json}")


def test_load_definition_rejects_missing_file_and_non_json_string() -> None:
    with pytest.raises(DefinitionLoadError, match="Could not load definition from path"):
        load_definition("missing-definition.asl.json")


def test_load_definition_requires_json_object() -> None:
    with pytest.raises(DefinitionLoadError, match="must decode to a JSON object"):
        load_definition('["not", "an", "object"]')


def test_load_definition_rejects_empty_string() -> None:
    with pytest.raises(DefinitionLoadError, match="cannot be empty"):
        load_definition("   ")


def test_load_definition_rejects_unsupported_object() -> None:
    with pytest.raises(DefinitionLoadError, match="must be a mapping"):
        load_definition(123)


def test_load_definition_rejects_non_serializable_mapping() -> None:
    with pytest.raises(DefinitionLoadError, match="JSON-serializable"):
        load_definition({"bad": object()})
