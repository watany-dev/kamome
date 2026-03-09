from __future__ import annotations

from typing import TYPE_CHECKING

import pytest_stepfunctions._dev as _dev

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from _pytest.capture import CaptureFixture
    from _pytest.monkeypatch import MonkeyPatch


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


def test_run_steps_returns_zero_when_all_commands_succeed() -> None:
    commands: list[tuple[tuple[str, ...], Path]] = []

    def fake_runner(command: Sequence[str], cwd: Path) -> int:
        commands.append((tuple(command), cwd))
        return 0

    return_code = _dev._run_steps(
        _dev.QUALITY_STEPS[:2],
        stream=_StringWriter(),
        command_runner=fake_runner,
    )

    assert return_code == 0
    assert commands == [
        (_dev.QUALITY_STEPS[0].command, _dev.PROJECT_ROOT),
        (_dev.QUALITY_STEPS[1].command, _dev.PROJECT_ROOT),
    ]


def test_main_rejects_arguments(capsys: CaptureFixture[str]) -> None:
    return_code = _dev.main(["--unexpected"])

    assert return_code == 2
    captured = capsys.readouterr()
    assert captured.err == "ci does not accept arguments.\n"


def test_security_main_uses_security_steps(monkeypatch: MonkeyPatch) -> None:
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


def test_emit_appends_newline_and_flushes_stream() -> None:
    stream = _StringWriter()

    _dev._emit("hello", stream=stream)

    assert stream.lines == ["hello\n"]
    assert stream.flush_count == 1


def test_normalize_argv_uses_explicit_args() -> None:
    assert _dev._normalize_argv(["--flag"]) == ["--flag"]


def test_normalize_argv_reads_sys_argv(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("pytest_stepfunctions._dev.sys.argv", ["ci", "--flag"])

    assert _dev._normalize_argv(None) == ["--flag"]


def test_run_command_sets_default_cache_root(monkeypatch: MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    class _CompletedProcess:
        returncode = 7

    def fake_run(
        command: Sequence[str],
        *,
        cwd: Path,
        check: bool,
        env: dict[str, str],
    ) -> _CompletedProcess:
        recorded["command"] = tuple(command)
        recorded["cwd"] = cwd
        recorded["check"] = check
        recorded["env"] = env
        return _CompletedProcess()

    monkeypatch.setattr("pytest_stepfunctions._dev.subprocess.run", fake_run)
    monkeypatch.setattr("pytest_stepfunctions._dev.os.environ", {})

    return_code = _dev._run_command(("python", "-V"), _dev.PROJECT_ROOT)

    assert return_code == 7
    assert recorded["command"] == ("python", "-V")
    assert recorded["cwd"] == _dev.PROJECT_ROOT
    assert recorded["check"] is False
    assert recorded["env"] == {"XDG_CACHE_HOME": str(_dev.CACHE_ROOT)}


def test_quality_steps_include_coverage_and_security() -> None:
    test_step = _dev.QUALITY_STEPS[3]
    audit_step = _dev.QUALITY_STEPS[-1]

    assert test_step.name == "Tests"
    assert "--cov-fail-under=95" in test_step.command
    assert "--cov-branch" in test_step.command
    assert audit_step == _dev.SECURITY_STEPS[0]


def test_py_typed_marker_exists() -> None:
    assert (_dev.PROJECT_ROOT / "src" / "pytest_stepfunctions" / "py.typed").is_file()


class _StringWriter:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.flush_count = 0

    def write(self, message: str) -> int:
        self.lines.append(message)
        return len(message)

    def flush(self) -> None:
        self.flush_count += 1
