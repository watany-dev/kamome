"""Definition loading and normalization helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any

from .exceptions import DefinitionLoadError


@dataclass(frozen=True, slots=True)
class NormalizedDefinition:
    """Loaded ASL document and its source label."""

    document: dict[str, Any]
    source_label: str


def load_definition(
    definition: object,
    *,
    definition_root: Path | None = None,
) -> NormalizedDefinition:
    """Load a definition from a mapping, JSON string, or filesystem path."""

    if isinstance(definition, Mapping):
        return NormalizedDefinition(
            document=_normalize_mapping(definition),
            source_label="<inline definition>",
        )

    if isinstance(definition, PathLike):
        path = _resolve_definition_path(Path(definition), definition_root=definition_root)
        return _load_definition_file(path)

    if isinstance(definition, str):
        text = definition.strip()
        if not text:
            msg = "Step Functions definition cannot be empty."
            raise DefinitionLoadError(msg)
        if text.startswith("{"):
            return NormalizedDefinition(
                document=_parse_definition_json(text, source_label="<inline JSON definition>"),
                source_label="<inline JSON definition>",
            )

        path = _resolve_definition_path(Path(text), definition_root=definition_root)
        if path.exists():
            return _load_definition_file(path)

        try:
            parsed = _parse_definition_json(text, source_label="<inline JSON definition>")
        except DefinitionLoadError as exc:
            msg = f"Could not load definition from path {text!r}, and it is not valid JSON: {exc}"
            raise DefinitionLoadError(msg) from exc
        return NormalizedDefinition(
            document=parsed,
            source_label="<inline JSON definition>",
        )

    msg = "Step Functions definition must be a mapping, filesystem path, or JSON string."
    raise DefinitionLoadError(msg)


def _resolve_definition_path(path: Path, *, definition_root: Path | None) -> Path:
    if path.is_absolute() or definition_root is None:
        return path
    return definition_root / path


def _load_definition_file(path: Path) -> NormalizedDefinition:
    if not path.exists():
        msg = f"Definition file not found: {path}"
        raise DefinitionLoadError(msg)
    try:
        contents = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - exercised by Python runtime
        msg = f"Could not read definition file {path}: {exc}"
        raise DefinitionLoadError(msg) from exc
    return NormalizedDefinition(
        document=_parse_definition_json(contents, source_label=str(path)),
        source_label=str(path),
    )


def _normalize_mapping(definition: Mapping[str, Any]) -> dict[str, Any]:
    try:
        serialized = json.dumps(dict(definition))
    except TypeError as exc:
        msg = f"Definition mapping must be JSON-serializable: {exc}"
        raise DefinitionLoadError(msg) from exc
    return _parse_definition_json(serialized, source_label="<inline definition>")


def _parse_definition_json(raw_json: str, *, source_label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        msg = f"Invalid JSON in {source_label}: {exc.msg}"
        raise DefinitionLoadError(msg) from exc
    if not isinstance(parsed, dict):
        msg = f"Step Functions definition from {source_label} must decode to a JSON object."
        raise DefinitionLoadError(msg)
    return parsed
