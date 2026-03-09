# Repository Guidance

## Project Overview

- This repository is for `pytest-stepfunctions`, a pytest plugin for testing AWS Step Functions.
- The project is still in the planning and documentation stage. There is no package scaffold or test runner configuration yet.
- `README.md` is the current product and API overview.
- `TODO.md` is the current implementation backlog and should stay aligned with any code or design changes.

## Working Agreements

- Keep the package name as `pytest-stepfunctions` and the import name as `pytest_stepfunctions` unless the user explicitly changes that decision.
- Prefer docs-first changes while the repository is still being scaffolded. If you define a feature in detail, update `README.md`, `TODO.md`, and add or update `docs/requirements.md` or `docs/design/*.md` as needed.
- Preserve the intended package layout from `TODO.md` when introducing code: `src/pytest_stepfunctions/` with the pytest plugin entry point.
- Be explicit about planned versus implemented behavior. Do not present roadmap items as already working.
- There are no authoritative build or test commands yet. If you add project tooling, update this file and `CLAUDE.md` with the exact commands and keep `README.md` consistent.

## Repo Skills

The following repo-local skills are available in this repository:

- `update-design`: Improve or create design docs for `pytest-stepfunctions`, score them critically, and close gaps before implementation. File: `/workspaces/kamome/.codex/skills/update-design/SKILL.md`
- `update-docs`: Sync `README.md`, `TODO.md`, and any design or requirements docs after implementation or scope changes. File: `/workspaces/kamome/.codex/skills/update-docs/SKILL.md`

Use these skills when the task is primarily about design documentation or keeping repository docs in sync with code and scope changes.
