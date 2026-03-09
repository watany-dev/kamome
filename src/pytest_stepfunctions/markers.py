"""Marker parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from .exceptions import ConfigurationError

MARKER_NAME = "sfn"
MARKER_DESCRIPTION = (
    "sfn(definition, name=None, backend=None, timeout=None): Step Functions test metadata"
)


@dataclass(frozen=True, slots=True)
class MarkerSettings:
    """Resolved settings from the closest ``sfn`` marker."""

    definition: object | None = None
    name: str | None = None
    backend: str | None = None
    timeout: int | None = None


class _MarkerLike(Protocol):
    args: tuple[object, ...]
    kwargs: dict[str, object]


class _NodeLike(Protocol):
    def get_closest_marker(self, name: str) -> object | None: ...


def extract_marker_settings(node: _NodeLike) -> MarkerSettings:
    """Read the nearest ``sfn`` marker and normalize its supported fields."""

    marker = cast("_MarkerLike | None", node.get_closest_marker(MARKER_NAME))
    if marker is None:
        return MarkerSettings()

    if len(marker.args) > 1:
        msg = "@pytest.mark.sfn accepts at most one positional argument for definition."
        raise ConfigurationError(msg)

    kwargs = dict(marker.kwargs)
    definition = kwargs.get("definition")
    if marker.args:
        if definition is not None:
            msg = "@pytest.mark.sfn definition cannot be provided twice."
            raise ConfigurationError(msg)
        definition = marker.args[0]

    name = _optional_str(kwargs.get("name"), field_name="name")
    backend = _optional_str(kwargs.get("backend"), field_name="backend")
    timeout = _optional_timeout(kwargs.get("timeout"))
    return MarkerSettings(
        definition=definition,
        name=name,
        backend=backend,
        timeout=timeout,
    )


def _optional_str(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    msg = f"sfn marker field {field_name!r} must be a string."
    raise ConfigurationError(msg)


def _optional_timeout(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        msg = "sfn marker field 'timeout' must be an integer."
        raise ConfigurationError(msg)
    if value <= 0:
        msg = "sfn marker field 'timeout' must be greater than zero."
        raise ConfigurationError(msg)
    return value
