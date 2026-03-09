from __future__ import annotations

import importlib
from dataclasses import dataclass

import pytest

import pytest_stepfunctions.markers as markers_module
from pytest_stepfunctions.exceptions import ConfigurationError
from pytest_stepfunctions.markers import extract_marker_settings


@dataclass
class _FakeMarker:
    args: tuple[object, ...]
    kwargs: dict[str, object]


class _FakeNode:
    def __init__(self, marker: _FakeMarker | None) -> None:
        self._marker = marker

    def get_closest_marker(self, name: str) -> _FakeMarker | None:
        assert name == "sfn"
        return self._marker


def test_markers_module_can_be_reloaded() -> None:
    assert importlib.reload(markers_module) is markers_module


def test_extract_marker_settings_supports_positional_definition() -> None:
    settings = extract_marker_settings(
        _FakeNode(_FakeMarker(args=({"StartAt": "Done", "States": {}},), kwargs={"timeout": 5}))
    )

    assert settings.definition == {"StartAt": "Done", "States": {}}
    assert settings.timeout == 5


def test_extract_marker_settings_rejects_duplicate_definition() -> None:
    with pytest.raises(ConfigurationError, match="provided twice"):
        extract_marker_settings(
            _FakeNode(
                _FakeMarker(
                    args=({"StartAt": "Done", "States": {}},),
                    kwargs={"definition": {"StartAt": "Other", "States": {}}},
                )
            )
        )


def test_extract_marker_settings_rejects_invalid_timeout() -> None:
    with pytest.raises(ConfigurationError, match="timeout"):
        extract_marker_settings(
            _FakeNode(_FakeMarker(args=(), kwargs={"definition": {}, "timeout": True}))
        )


def test_extract_marker_settings_returns_empty_settings_without_marker() -> None:
    settings = extract_marker_settings(_FakeNode(None))

    assert settings.definition is None
    assert settings.backend is None


def test_extract_marker_settings_rejects_multiple_positional_args() -> None:
    with pytest.raises(ConfigurationError, match="at most one positional argument"):
        extract_marker_settings(_FakeNode(_FakeMarker(args=({"one": 1}, {"two": 2}), kwargs={})))


def test_extract_marker_settings_rejects_non_string_name() -> None:
    with pytest.raises(ConfigurationError, match="must be a string"):
        extract_marker_settings(_FakeNode(_FakeMarker(args=(), kwargs={"name": 1})))
