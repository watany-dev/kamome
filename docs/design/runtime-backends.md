# runtime backend 設計

## 概要

この設計書は、`pytest-stepfunctions` の scaffold 後に追加した runtime 実装をまとめる。
対象は definition ロード、設定解決、backend 抽象、`local` / `teststate` backend、validation、fixture 配線である。

## 公開 interface

公開 API は次に固定する。

- marker: `@pytest.mark.sfn(definition, name=None, backend=None, timeout=None)`
- fixture:
  - `sfn_run(scenario, *, definition=None, name=None, backend=None, timeout=None, validate=None, region=None, local_endpoint=None, role_arn=None, definition_root=None, mock_config=None)`
  - `sfn_test_state(*, definition=None, state_name, input, backend=None, timeout=None, validate=None, region=None, local_endpoint=None, role_arn=None, definition_root=None, mock_config=None)`
- dataclass:
  - `Scenario`
  - `ExecutionResult`

`Scenario` と `ExecutionResult` は引き続き公開モデルとし、runtime 用の spec は内部モデルに留める。

## definition と設定解決

`definition` は次の 3 形態を受ける。

1. filesystem path
2. `dict`
3. JSON string

ロード後は JSON object に正規化する。YAML は未対応のまま据え置く。

設定優先順位は次に固定する。

1. fixture 呼び出し引数
2. marker
3. CLI
4. `pyproject.toml`
5. デフォルト値

`backend="auto"` は次の規則で固定する。

- `sfn_run`: `local`
- `sfn_test_state`: `teststate`

## backend 設計

### `local`

- Step Functions Local endpoint を使う
- state machine は都度 `CreateStateMachine` し、実行後に `DeleteStateMachine` する
- `Scenario.case` がある場合は `stateMachineArn#CaseName` を `StartExecution` に渡す
- `DescribeExecution` を polling して terminal status まで待つ
- timeout 超過時は `ExecutionTimeoutError` を上げる
- `sfn_mock_config` がある場合だけ test case 名の存在確認を行う

### `teststate`

- AWS `TestState` API を使う
- 現在の実装は `definition + state_name + input + role_arn` を基本入力とする
- plugin 内の rate limit 制御はまだ入れない
- `status` / `output` / `error` / `cause` / `nextState` を `ExecutionResult` に写す

### `aws`

- v0.1 では stub のみ
- backend choice と将来の拡張点だけ残す

## validation とエラーモデル

- validation は opt-in とし、`validate=True` または `sfn_validate=true` のときだけ実行する
- `ValidateStateMachineDefinition` の結果は `ValidationResult` / `Diagnostic` に正規化する
- 失敗時は `ValidationError` を投げる

runtime で使う主要例外:

- `ConfigurationError`
- `BackendResolutionError`
- `DefinitionLoadError`
- `ValidationError`
- `BackendError`
- `BackendNotImplementedError`
- `ExecutionTimeoutError`
- `MockCaseNotFoundError`

fixture ではこれらを捕まえて `pytest.fail(..., pytrace=False)` に変換する。

## テスト方針

- unit test で definition ロード、設定優先順位、backend resolver、validation、例外変換を確認する
- `pytester` を使って plugin 読込、marker 表示、CLI 表示、fixture 実行を確認する
- `tutorials/order_status/` に Step Functions Local と AWS `TestState` の手動チュートリアルを置く
- tutorial は実 backend を触る利用例であり、integration test や常設 CI job の代替にはしない
- `src/pytest_stepfunctions` の branch coverage を 95% 以上で維持する

## 残課題

- Step Functions Local integration test
- AWS `TestState` の opt-in integration test
- mock config のより深い検証
- `TestState` の rate limit / xdist 方針
- `aws` backend の正式実装
