"""Backend factory helpers."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from ..exceptions import BackendResolutionError
from .aws import AwsBackend
from .local import LocalBackend
from .teststate import TestStateBackend

if TYPE_CHECKING:
    from ..config import ResolvedConfig
    from .base import Backend

_SUPPORTED_BACKENDS = {"local", "teststate", "aws"}


def resolve_backend_name(requested_backend: str, *, state_name: str | None = None) -> str:
    """Resolve ``auto`` to a concrete backend name."""

    if requested_backend == "auto":
        return "teststate" if state_name is not None else "local"
    if requested_backend not in _SUPPORTED_BACKENDS:
        msg = f"Unsupported Step Functions backend {requested_backend!r}."
        raise BackendResolutionError(msg)
    return requested_backend


def create_backend(
    requested_backend: str, *, config: ResolvedConfig, state_name: str | None
) -> Backend:
    """Instantiate the requested backend."""

    backend_name = resolve_backend_name(requested_backend, state_name=state_name)
    resolved_config = replace(config, backend=backend_name)
    if backend_name == "local":
        return LocalBackend(resolved_config)
    if backend_name == "teststate":
        return TestStateBackend(resolved_config)
    return AwsBackend(resolved_config)
