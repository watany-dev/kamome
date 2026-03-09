"""Development-only command entry points for repository guardrails."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = PROJECT_ROOT / ".cache"
PYTHON = sys.executable


@dataclass(frozen=True, slots=True)
class Step:
    """A named command executed by the local CI entry points."""

    name: str
    command: tuple[str, ...]


class CommandRunner(Protocol):
    def __call__(self, command: Sequence[str], cwd: Path) -> int: ...


class OutputStream(Protocol):
    def write(self, message: str) -> int: ...

    def flush(self) -> None: ...


QUALITY_STEPS: tuple[Step, ...] = (
    Step("Format check", (PYTHON, "-m", "ruff", "format", "--check", ".")),
    Step("Lint", (PYTHON, "-m", "ruff", "check", ".")),
    Step("Type check", (PYTHON, "-m", "mypy", "src", "tests")),
    Step(
        "Tests",
        (
            PYTHON,
            "-m",
            "pytest",
            "--cov=pytest_stepfunctions",
            "--cov-branch",
            "--cov-report=term-missing",
            "--cov-fail-under=95",
        ),
    ),
    Step("Build", (PYTHON, "-m", "build", "--no-isolation")),
    Step(
        "Dead code",
        (PYTHON, "-m", "vulture", "src", "tests", "tools/vulture_whitelist.py"),
    ),
    Step("Dependency audit", (PYTHON, "-m", "pip_audit")),
)

SECURITY_STEPS: tuple[Step, ...] = (Step("Dependency audit", (PYTHON, "-m", "pip_audit")),)


def _emit(message: str, *, stream: OutputStream) -> None:
    stream.write(f"{message}\n")
    stream.flush()


def _run_command(command: Sequence[str], cwd: Path) -> int:
    environment = os.environ.copy()
    environment.setdefault("XDG_CACHE_HOME", str(CACHE_ROOT))
    completed = subprocess.run(command, cwd=cwd, check=False, env=environment)
    return completed.returncode


def _run_steps(
    steps: Sequence[Step],
    *,
    stream: OutputStream,
    command_runner: CommandRunner = _run_command,
) -> int:
    for step in steps:
        _emit(f"[ci] {step.name}", stream=stream)
        return_code = command_runner(step.command, PROJECT_ROOT)
        if return_code != 0:
            return return_code
    return 0


def _normalize_argv(argv: Sequence[str] | None) -> list[str]:
    return list(sys.argv[1:] if argv is None else argv)


def _run_entrypoint(
    command_name: str,
    steps: Sequence[Step],
    argv: Sequence[str] | None = None,
    *,
    stream: OutputStream = sys.stdout,
) -> int:
    arguments = _normalize_argv(argv)
    if arguments:
        _emit(f"{command_name} does not accept arguments.", stream=sys.stderr)
        return 2
    return _run_steps(steps, stream=stream)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the repository's standard quality gate locally."""

    return _run_entrypoint("ci", QUALITY_STEPS, argv)


def security_main(argv: Sequence[str] | None = None) -> int:
    """Run the repository's supplemental dependency audit locally."""

    return _run_entrypoint("ci-security", SECURITY_STEPS, argv)
