# pytest-stepfunctions v0.1 要件メモ

## 目的

`pytest-stepfunctions` は、AWS Step Functions を `pytest` から扱うための plugin として、次を実現する。

- ASL 定義の壊れを早く検知できること
- 分岐、retry、catch を CI 上で再現しやすいこと
- Step Functions Local と AWS `TestState` を同じテストスタイルで扱えること

## v0.1 で固定した前提

- パッケージ名は `pytest-stepfunctions`
- import 名は `pytest_stepfunctions`
- Python 対応は 3.10 から 3.13
- 最低依存は `pytest>=8.0`、`boto3>=1.34`
- 開発ワークフローは `uv`

## v0.1 のスコープ

- Python package scaffold
- `pytest11` entry point
- `sfn` marker
- `--sfn-*` CLI オプション
- `Scenario` / `ExecutionResult`
- `sfn_run` / `sfn_test_state` fixture の scaffold
- `uv run ci` を正本とする品質ゲート
- lint、format check、type check、coverage 付き unit/plugin test、build、dead code check、dependency audit を回す CI

## v0.1 の非スコープ

- `local` backend の本実装
- `teststate` backend の本実装
- definition ロードと設定優先順位の本実装
- Step Functions Local integration test
- AWS `TestState` 常設 CI

## backend 方針

- `local`: v0.1 の主対象だが、今回の実装は scaffold まで
- `teststate`: v0.1 の主対象だが、今回の実装は scaffold まで
- `aws`: v0.1 では stub のみ

## 品質ルール

- `uv run ci` を提出前の必須コマンドとして扱う
- `src/pytest_stepfunctions` は branch coverage 95% 以上を維持する
- `pytest` は `--strict-config` と `--strict-markers` を有効にする
- `mypy` は `strict = true` に加えて未使用 ignore、冗長 cast、`Any` 返却、暗黙 re-export なども警告対象にする
- `ruff` は import 整列、注釈、例外、type-checking import、path 操作などを含む広めのルール集合を使う
