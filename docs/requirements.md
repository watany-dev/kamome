# pytest-stepfunctions v0.1 要件メモ

## 目的

`pytest-stepfunctions` は、AWS Step Functions を `pytest` から扱うための plugin として、次を実現する。

- ASL 定義の壊れを早く検知できること
- 分岐、retry、catch を CI 上で再現しやすいこと
- Step Functions Local と AWS `TestState` を同じテストスタイルで扱えること

## 現在の実装スコープ

- `pytest11` entry point
- `sfn` marker
- `--sfn-*` CLI オプション
- `pyproject.toml` の `sfn_*` 設定
- `Scenario` / `ExecutionResult`
- `ExecutionSpec` / `StateTestSpec` / `ValidationResult` / diagnostics
- `sfn_run` / `sfn_test_state` fixture の本実装
- definition ロード
  - path
  - `dict`
  - JSON string
- 設定優先順位の解決
- `local` backend の最小実装
- `teststate` backend の最小実装
- `aws` backend の `sfn_run` 実装
- optional validation
- `tutorials/order_status/` の手動チュートリアル
- Step Functions Local integration test
- AWS `TestState` opt-in integration test
- AWS `sfn_run` opt-in integration test
- GitHub Actions の dedicated Local integration job
- `uv run ci` を正本とする品質ゲート

## 非スコープ

- `aws` backend の `sfn_test_state` 対応
- AWS `TestState` integration test の常設 CI
- YAML definition 対応
- `TestState` のレート制御
- xdist 連携
- mock config の詳細 lint

## backend 方針

- `local`: `sfn_run` の主 backend。Step Functions Local に state machine を都度作成して実行し、実行後に削除する
- `teststate`: `sfn_test_state` の主 backend。AWS `TestState` API を直接呼ぶ
- `aws`: `sfn_run` 用の実 backend。AWS 上に state machine を都度作成して実行し、timeout 時は `StopExecution` を試みてから削除する

## 公開 API 方針

- 実行 API は fixture に寄せる
- 静的設定は marker に寄せる
- backend 差分は `ExecutionResult` に吸収する
- 設定は `fixture > marker > CLI > pyproject > default` で解決する

## 制約

- `local` backend は Step Functions Local が事前起動されていることを前提とする
- `teststate` backend は `role_arn` を必須とする
- `tests/integration/test_teststate_backend.py` は `PYTEST_STEPFUNCTIONS_RUN_TESTSTATE_INTEGRATION=1` と `role_arn` 設定がある場合のみ実行する
- `aws` backend は `role_arn` を必須とし、`Scenario.case` / `sfn_mock_config` / `--sfn-local-endpoint` を受け付けない
- `tests/integration/test_aws_backend.py` は `PYTEST_STEPFUNCTIONS_RUN_AWS_INTEGRATION=1` と `role_arn` 設定がある場合のみ実行する
- validation は AWS `ValidateStateMachineDefinition` へ到達できる認証情報が必要
- `Scenario.case` の事前検証は `sfn_mock_config` が設定されている場合のみ行う
- tutorial は学習用の手動実行資材であり、通常の CI 対象ではない
- `aws` backend で必要になる最小権限は `states:CreateStateMachine`、`states:StartExecution`、`states:DescribeExecution`、`states:DeleteStateMachine`、`states:StopExecution`、`iam:PassRole`

## 品質ルール

- `uv run ci` を提出前の必須コマンドとして扱う
- `src/pytest_stepfunctions` は branch coverage 95% 以上を維持する
- `pytest` は `--strict-config` と `--strict-markers` を有効にする
- `mypy` は `strict = true` を維持する
- `ruff`、`build`、`vulture`、`pip-audit` を CI に含める
