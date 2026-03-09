from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

if TYPE_CHECKING:
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

    result = pytester.runpytest("--markers")

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

    result = pytester.runpytest("-q")

    result.stdout.fnmatch_lines(
        [
            "*sfn_run is scaffolded but not implemented yet.*",
            "*sfn_test_state is scaffolded but not implemented yet.*",
        ]
    )
    assert result.ret == 1


def test_cli_options_are_exposed_in_help(pytester: pytest.Pytester) -> None:
    result = pytester.runpytest("--help")

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


def test_invalid_backend_choice_fails_with_usage_error(pytester: pytest.Pytester) -> None:
    result = pytester.runpytest("--sfn-backend=invalid")

    result.stderr.fnmatch_lines(["*invalid choice: 'invalid'*"])
    assert result.ret == 4


def test_project_scripts_are_declared() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]

    assert scripts["ci"] == "pytest_stepfunctions._dev:main"
    assert scripts["ci-security"] == "pytest_stepfunctions._dev:security_main"


def test_dev_dependencies_cover_quality_tooling() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]

    assert any(dependency.startswith("ruff") for dependency in dev_dependencies)
    assert any(dependency.startswith("mypy") for dependency in dev_dependencies)
    assert any(dependency.startswith("vulture") for dependency in dev_dependencies)
    assert any(dependency.startswith("pip-audit") for dependency in dev_dependencies)
