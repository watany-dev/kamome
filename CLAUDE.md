# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

`pytest-stepfunctions` is a pytest plugin for testing AWS Step Functions.

Current project status:

- The repository is still documentation-first.
- `README.md` describes the intended public API and product direction.
- `TODO.md` is the implementation backlog and planned package layout.
- Source code, packaging metadata, and CI configuration have not been created yet.

## Current Working Rules

- Keep the package name as `pytest-stepfunctions`.
- Keep the import name as `pytest_stepfunctions`.
- Treat `local` and `teststate` as the primary early backends.
- Do not assume the `aws` backend is in scope for the first release unless the user explicitly decides that.
- Keep roadmap statements clearly separated from implemented behavior.

## Commands

There are no project-specific build, lint, or test commands configured yet.

Until scaffolding exists, the minimum completion bar is:

1. Keep `README.md` and `TODO.md` consistent with the change.
2. If a design is introduced or changed, add or update `docs/requirements.md` or `docs/design/*.md`.
3. If you add tooling such as `pyproject.toml`, test configuration, or CI, document the exact commands here and in `AGENTS.md`.

## Project Principles

### Public API

- Prefer pytest-native APIs: fixtures, markers, and parametrized scenarios.
- Keep backend differences behind shared result models and stable user-facing fixtures.
- Optimize for clear failure messages and reproducible tests in CI.

### Development Style

- Use TDD when implementing features: Red, Green, Refactor.
- Separate structural cleanup from behavioral changes when practical.
- Favor small, reviewable iterations instead of broad speculative scaffolding.

### Documentation Discipline

- `README.md` should describe the current user-facing contract.
- `TODO.md` should describe the remaining work, not duplicate already finished work.
- Design documents should be concrete enough that implementation can start without hidden assumptions.
