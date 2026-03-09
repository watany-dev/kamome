from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

import pytest


def test_pytest11_entrypoint_is_declared() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    pytest11 = pyproject["project"]["entry-points"]["pytest11"]

    assert pytest11["pytest_stepfunctions"] == "pytest_stepfunctions.plugin"


def test_marker_registration_is_visible(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_placeholder():
            assert True
        """
    )

    result = pytester.runpytest("-p", "pytest_stepfunctions.plugin", "--markers")

    result.stdout.fnmatch_lines(
        [
            "*@pytest.mark.sfn(definition, name=None, backend=None, timeout=None):*",
        ]
    )
    assert result.ret == 0


def test_stub_fixtures_fail_with_actionable_message(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_sfn_run_stub(sfn_run):
            sfn_run({"input": "ignored"})

        def test_sfn_test_state_stub(sfn_test_state):
            sfn_test_state(definition={}, state_name="CheckStatus", input={})
        """
    )

    result = pytester.runpytest("-p", "pytest_stepfunctions.plugin", "-q")

    result.stdout.fnmatch_lines(
        [
            "*sfn_run is scaffolded but not implemented yet.*",
            "*sfn_test_state is scaffolded but not implemented yet.*",
        ]
    )
    assert result.ret == 1


def test_cli_options_are_exposed_in_help(pytester: pytest.Pytester) -> None:
    result = pytester.runpytest("-p", "pytest_stepfunctions.plugin", "--help")

    result.stdout.fnmatch_lines(
        [
            "*--sfn-backend*",
            "*--sfn-region*",
            "*--sfn-local-endpoint*",
            "*--sfn-role-arn*",
            "*--sfn-definition-root*",
            "*--sfn-mock-config*",
            "*--sfn-validate*",
        ]
    )
    assert result.ret == 0
