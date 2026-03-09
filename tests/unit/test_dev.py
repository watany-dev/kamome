from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from pytest_stepfunctions import _dev


def test_run_steps_stops_after_first_failure() -> None:
    commands: list[tuple[tuple[str, ...], Path]] = []

    def fake_runner(command: Sequence[str], cwd: Path) -> int:
        commands.append((tuple(command), cwd))
        return 1 if len(commands) == 2 else 0

    return_code = _dev._run_steps(
        _dev.QUALITY_STEPS[:3],
        stream=_StringWriter(),
        command_runner=fake_runner,
    )

    assert return_code == 1
    assert commands == [
        (_dev.QUALITY_STEPS[0].command, _dev.PROJECT_ROOT),
        (_dev.QUALITY_STEPS[1].command, _dev.PROJECT_ROOT),
    ]


def test_main_rejects_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    return_code = _dev.main(["--unexpected"])

    assert return_code == 2
    captured = capsys.readouterr()
    assert captured.err == "ci does not accept arguments.\n"


def test_security_main_uses_security_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, tuple[_dev.Step, ...]] = {}

    def fake_run_steps(
        steps: Sequence[_dev.Step],
        *,
        stream: _dev.OutputStream,
        command_runner: _dev.CommandRunner = _dev._run_command,
    ) -> int:
        del stream, command_runner
        recorded["steps"] = tuple(steps)
        return 0

    monkeypatch.setattr(_dev, "_run_steps", fake_run_steps)

    return_code = _dev.security_main([])

    assert return_code == 0
    assert recorded["steps"] == _dev.SECURITY_STEPS


def test_py_typed_marker_exists() -> None:
    assert (_dev.PROJECT_ROOT / "src" / "pytest_stepfunctions" / "py.typed").is_file()


class _StringWriter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, message: str) -> int:
        self.lines.append(message)
        return len(message)

    def flush(self) -> None:
        return None
