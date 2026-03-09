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
- `sfn_mock_config` がある場合は root object / `StateMachines` / 各 `TestCases` の JSON 構造を実行前に検査する
- `DescribeExecution` を polling して terminal status まで待つ
- timeout 超過時は `ExecutionTimeoutError` を上げる
- `Scenario.case` と `sfn_mock_config` を併用した場合だけ test case 名の存在確認を行う

### `teststate`

- AWS `TestState` API を使う
- 現在の実装は `definition + state_name + input + role_arn` を基本入力とする
- inspection level は alpha では `INFO` に固定する
- plugin 内の rate limit 制御は alpha では入れない
- `status` / `output` / `error` / `cause` / `nextState` を `ExecutionResult` に写す

### `aws`

- `sfn_run` 用 backend として AWS Step Functions を使う
- state machine はテストごとに一時作成し、実行後に `DeleteStateMachine` する
- `DescribeExecution` を polling して terminal status まで待つ
- timeout 超過時は `StopExecution` を best effort で呼んでから `ExecutionTimeoutError` を上げる
- `role_arn` を必須とする
- `Scenario.case`、`sfn_mock_config`、`--sfn-local-endpoint` は local 専用として拒否する
- alpha では `sfn_test_state` に対応しない。state 単体は `teststate` backend を使う

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
- `tests/integration/test_local_backend.py` で Step Functions Local を使う実統合確認を行う
- `tests/integration/test_teststate_backend.py` で AWS `TestState` を使う opt-in 実統合確認を行う
- `tests/integration/test_aws_backend.py` で AWS `sfn_run` の opt-in 実統合確認を行う
- GitHub Actions では `local-integration` job で Step Functions Local を起動して上記 integration test を実行する
- GitHub Actions では tag 起点の publish workflow で PyPI へ配布する
- `tutorials/order_status/` に Step Functions Local と AWS `TestState` の手動チュートリアルを置く
- tutorial は実 backend を触る利用例であり、integration test や常設 CI job の代替にはしない
- `src/pytest_stepfunctions` の branch coverage を 95% 以上で維持する

## 残課題

- mock config の semantic lint
- `TestState` の rate limit / xdist 方針
- `aws` backend の再利用モードや `sfn_test_state` 対応方針
