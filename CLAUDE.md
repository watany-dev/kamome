# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

`pytest-stepfunctions` is a pytest plugin for testing AWS Step Functions.

Current project status:

- The repository has an initial package scaffold, pytest plugin entry point, plugin tests, and CI.
- `README.md` describes both the implemented scaffold and the intended public API direction.
- `TODO.md` is the implementation backlog and planned package layout.
- Runtime backends and config resolution are still unimplemented.

## Current Working Rules

- Keep the package name as `pytest-stepfunctions`.
- Keep the import name as `pytest_stepfunctions`.
- Treat `local` and `teststate` as the primary early backends.
- Do not assume the `aws` backend is in scope for the first release unless the user explicitly decides that.
- Keep roadmap statements clearly separated from implemented behavior.

## Commands

There are no project-specific build, lint, or test commands configured yet.

Authoritative commands:

1. `uv sync --extra dev`
2. `uv run pytest`
3. `uv run ruff check .`
4. `uv run ruff format --check .`
5. `uv run mypy src tests`
6. `uv run python -m build`

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
