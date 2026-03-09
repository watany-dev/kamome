# Repository Guidance

## Project Overview

- This repository is for `pytest-stepfunctions`, a pytest plugin for testing AWS Step Functions.
- The repository now has an initial Python package scaffold, pytest plugin entry point, basic tests, and CI.
- Runtime backends are not implemented yet; `README.md` must keep implemented scaffold and planned behavior clearly separated.
- `README.md` is the current product and API overview.
- `TODO.md` is the current implementation backlog and should stay aligned with any code or design changes.

## Working Agreements

- Keep the package name as `pytest-stepfunctions` and the import name as `pytest_stepfunctions` unless the user explicitly changes that decision.
- Keep `README.md`, `TODO.md`, `docs/requirements.md`, and `docs/design/*.md` synchronized with code and scope changes.
- Preserve the intended package layout from `TODO.md` when introducing code: `src/pytest_stepfunctions/` with the pytest plugin entry point.
- Be explicit about planned versus implemented behavior. Do not present roadmap items as already working.

## Commands

- Install dev environment: `uv sync --extra dev`
- Run tests: `uv run pytest`
- Run lint: `uv run ruff check .`
- Check formatting: `uv run ruff format --check .`
- Run type checks: `uv run mypy src tests`
- Build package: `uv run python -m build`

## Repo Skills

The following repo-local skills are available in this repository:

- `update-design`: Improve or create design docs for `pytest-stepfunctions`, score them critically, and close gaps before implementation. File: `/workspaces/kamome/.codex/skills/update-design/SKILL.md`
- `update-docs`: Sync `README.md`, `TODO.md`, and any design or requirements docs after implementation or scope changes. File: `/workspaces/kamome/.codex/skills/update-docs/SKILL.md`

Use these skills when the task is primarily about design documentation or keeping repository docs in sync with code and scope changes.
