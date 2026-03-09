"""Stub AWS backend."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..exceptions import BackendNotImplementedError
from .base import Backend

if TYPE_CHECKING:
    from ..model import ExecutionResult, ExecutionSpec, StateTestSpec


class AwsBackend(Backend):
    """Placeholder for the future AWS backend."""

    name = "aws"

    def run(self, spec: ExecutionSpec) -> ExecutionResult:
        del spec
        msg = "The aws backend is not implemented yet."
        raise BackendNotImplementedError(msg)

    def test_state(self, spec: StateTestSpec) -> ExecutionResult:
        del spec
        msg = "The aws backend is not implemented yet."
        raise BackendNotImplementedError(msg)
