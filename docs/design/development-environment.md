# 開発環境 scaffold 設計

## 概要

この設計書は、`pytest-stepfunctions` の v0.1 着手前に必要な開発環境と plugin 骨組みを定義する。
対象は「開発を始められること」であり、Step Functions backend の実行機能そのものはまだ含めない。

## 到達点

この段階で満たすべき状態は次のとおり。

- `pyproject.toml` で package build と開発ツール設定ができる
- `src/pytest_stepfunctions/` で package import と plugin entry point が成立する
- `Scenario` と `ExecutionResult` を import できる
- `sfn` marker と `--sfn-*` CLI オプションが pytest から見える
- `sfn_run` と `sfn_test_state` が fixture として解決できる
- fixture を呼び出したとき、未実装であることが明確な失敗になる
- `uv run ci` で format、lint、type check、coverage、build、dead code、dependency audit を一括実行できる

## 非スコープ

この段階では次を実装しない。

- ASL definition のロード
- 設定優先順位の解決
- `local` / `teststate` backend の実行
- Step Functions Local を使う integration test
- AWS 認証付き workflow

## 技術判断

### Python とツール

- Python 対応: 3.10-3.13
- build backend: `hatchling`
- 開発ワークフロー: `uv`
- formatter / linter: `ruff`
- type checker: `mypy`
- test runner: `pytest`

### package layout

```text
src/
  pytest_stepfunctions/
    __init__.py
    model.py
    plugin.py
    helpers/
      __init__.py
      assertions.py
tests/
  plugin/
  unit/
```

`TODO.md` にある将来ファイル群はまだ作らない。実装がないファイルを空のまま増やさず、必要最小限の骨組みに留める。

## 公開 interface

### dataclass

- `Scenario`
  `id`
  `input`
  `case`
  `name`
  `timeout`
- `ExecutionResult`
  `status`
  `backend`
  `execution_arn`
  `output_json`
  `error`
  `cause`
  `next_state`
  `raw`
  `assert_status()`
  `assert_succeeded()`
  `assert_failed()`

### pytest plugin

- entry point: `pytest_stepfunctions.plugin`
- marker: `@pytest.mark.sfn(definition, name=None, backend=None, timeout=None)`
- fixture: `sfn_run`, `sfn_test_state`
- CLI:
  `--sfn-backend`
  `--sfn-region`
  `--sfn-local-endpoint`
  `--sfn-role-arn`
  `--sfn-definition-root`
  `--sfn-mock-config`
  `--sfn-validate`

### 未実装時の振る舞い

`sfn_run` と `sfn_test_state` は callable を返すが、呼び出すと `pytest.fail(..., pytrace=False)` で失敗させる。
`skip` にしない理由は、scaffold 状態を CI 上の見逃しにしないため。

## テスト戦略

### unit test

- `Scenario` のフィールド保持を確認する
- `Scenario` が frozen dataclass であることを確認する
- `ExecutionResult` の assertion メソッドを確認する
- 公開 package export と assertion rewrite 登録を確認する

### plugin test

- `pytest11` entry point が宣言されていること
- `--markers` に `sfn` marker が出ること
- `--help` に CLI オプションが出ること
- 不正な backend choice が usage error になること
- `sfn_run` / `sfn_test_state` が解決し、未実装メッセージで失敗すること

### CI

GitHub Actions では次を回す。

- `uv sync --extra dev`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy src tests`
- `uv run pytest --cov=pytest_stepfunctions --cov-branch --cov-fail-under=95`
- `uv run python -m build --no-isolation`
- `uv run vulture src tests tools/vulture_whitelist.py`
- `uv run pip-audit`

## 後続実装への引き継ぎ

次段で優先するのは次の順にする。

1. definition ロードと正規化
2. 設定優先順位の解決
3. backend abstraction
4. `local` backend
5. `teststate` backend

`aws` backend は v0.1 では stub のまま据え置く。
