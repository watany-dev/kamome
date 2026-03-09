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


def test_sfn_run_executes_local_backend(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest
        from pytest_stepfunctions import Scenario

        class FakeClient:
            def create_state_machine(self, **kwargs):
                return {"stateMachineArn": "arn:aws:states:local:stateMachine:OrderFlow"}

            def start_execution(self, **kwargs):
                assert kwargs["stateMachineArn"].endswith("#HappyPath")
                return {"executionArn": "arn:aws:states:local:execution:OrderFlow:exec-1"}

            def describe_execution(self, **kwargs):
                return {"status": "SUCCEEDED", "output": '{"status": "paid"}'}

            def delete_state_machine(self, **kwargs):
                return None

        @pytest.mark.sfn(
            definition={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
            name="OrderFlow",
        )
        def test_sfn_run_executes(monkeypatch, sfn_run):
            monkeypatch.setattr(
                "pytest_stepfunctions.backends.base.boto3.client",
                lambda *args, **kwargs: FakeClient(),
            )
            result = sfn_run(
                Scenario(id="happy", input={"orderId": "o-1"}, case="HappyPath", name="exec-1")
            )

            result.assert_succeeded()
            assert result.output_json == {"status": "paid"}
        """
    )

    result = pytester.runpytest("-q")

    result.stdout.fnmatch_lines(["*1 passed*"])
    assert result.ret == 0


def test_sfn_test_state_executes_teststate_backend(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        class FakeClient:
            def test_state(self, **kwargs):
                assert kwargs["stateName"] == "CheckStatus"
                return {
                    "status": "SUCCEEDED",
                    "output": '{"status": "PAID"}',
                    "nextState": "Complete",
                }

        def test_sfn_test_state_executes(monkeypatch, sfn_test_state):
            monkeypatch.setattr(
                "pytest_stepfunctions.backends.base.boto3.client",
                lambda *args, **kwargs: FakeClient(),
            )
            result = sfn_test_state(
                definition={
                    "StartAt": "CheckStatus",
                    "States": {"CheckStatus": {"Type": "Succeed"}},
                },
                state_name="CheckStatus",
                input={"status": "PAID"},
                role_arn="arn:aws:iam::123456789012:role/TestStateRole",
            )

            result.assert_succeeded()
            assert result.next_state == "Complete"
        """
    )

    result = pytester.runpytest("-q")

    result.stdout.fnmatch_lines(["*1 passed*"])
    assert result.ret == 0


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
