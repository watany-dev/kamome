# pytest-stepfunctions

`pytest-stepfunctions` は、AWS Step Functions を `pytest` からテストするための pytest plugin です。

このリポジトリでは、次の 3 つを主な目的にしています。

- ASL 定義の壊れを早く検知する
- 分岐、retry、catch を CI 上で再現可能にする
- Step Functions Local と AWS `TestState` を pytest らしい形で使い分けられるようにする

現在の公開候補は Public PyPI 向け alpha `0.1.0a1` です。変更履歴は [`CHANGELOG.md`](CHANGELOG.md)、maintainer 向け公開手順は [`docs/release.md`](docs/release.md) を参照してください。

## 現在のステータス

現時点で実装済みのもの:

- `pytest11` entry point による plugin 自動読込
- `sfn` marker と `--sfn-*` CLI オプション
- `Scenario` / `ExecutionResult` の公開 dataclass
- `definition` のロードと正規化
  - ファイルパス
  - `dict`
  - JSON 文字列
- 設定優先順位の解決
  1. fixture 呼び出し引数
  2. marker
  3. CLI
  4. `pyproject.toml`
  5. デフォルト値
- `backend="auto"` の解決
  - `sfn_run` は `local`
  - `sfn_test_state` は `teststate`
- `local` backend の最小実装
  - Step Functions Local への state machine 作成
  - `Scenario.case` の `stateMachineArn#CaseName` 変換
  - `sfn_mock_config` の JSON 構造検査と test case 存在確認
  - 実行完了待ち
  - timeout 監視
  - 実行後の state machine 削除
- `teststate` backend の最小実装
  - AWS `TestState` API 呼び出し
  - `ExecutionResult` への正規化
- `aws` backend の最小実装
  - AWS Step Functions への state machine 作成
  - 実行完了待ち
  - timeout 時の `StopExecution`
  - 実行後の state machine 削除
- AWS `TestState` を使う opt-in integration test
  - `tests/integration/test_teststate_backend.py`
- AWS Step Functions を使う opt-in integration test
  - `tests/integration/test_aws_backend.py`
- `ValidateStateMachineDefinition` を使う optional validation
- `tutorials/order_status/` の手動チュートリアル
  - Step Functions Local を使う `sfn_run` サンプル
  - AWS `TestState` を使う `sfn_test_state` サンプル
- Step Functions Local を使う integration test
  - `tests/integration/test_local_backend.py`
  - GitHub Actions の `local-integration` job
- `uv run ci` を正本とする品質ゲート

まだ未実装のもの:

- `aws` backend の `sfn_test_state` 対応
- AWS `TestState` の常設 CI job
- YAML definition 対応
- `TestState` のスロットリングや xdist 連携
- mock config の semantic lint

## インストール

利用者向けの最終形は次を想定しています。

```bash
pip install pytest-stepfunctions
```

開発参加時は `uv` を使います。

```bash
uv sync --extra dev
```

## Quick Start

### state machine 実行

```python
import pytest
from pytest_stepfunctions import Scenario

pytestmark = pytest.mark.sfn(
    definition="tests/workflows/order_flow.asl.json",
    name="OrderFlow",
)

@pytest.mark.parametrize(
    "scenario",
    [
        Scenario(id="happy", input={"orderId": "o-1"}, case="HappyPath"),
        Scenario(id="payment_timeout", input={"orderId": "o-1"}, case="PaymentFails"),
    ],
    ids=lambda s: s.id,
)
def test_order_flow(sfn_run, scenario):
    result = sfn_run(scenario)

    if scenario.id == "happy":
        result.assert_succeeded()
    else:
        result.assert_failed("Payment.Timeout")
```

### state 単体テスト

```python
def test_check_status_paid(sfn_test_state):
    result = sfn_test_state(
        definition={
            "StartAt": "CheckStatus",
            "States": {
                "CheckStatus": {
                    "Type": "Choice",
                    "Choices": [
                        {
                            "Variable": "$.status",
                            "StringEquals": "PAID",
                            "Next": "Complete",
                        }
                    ],
                    "Default": "Reject",
                },
                "Complete": {"Type": "Succeed"},
                "Reject": {"Type": "Fail", "Error": "Order.NotPaid"},
            },
        },
        state_name="CheckStatus",
        input={"status": "PAID"},
        role_arn="arn:aws:iam::123456789012:role/StepFunctionsTestRole",
    )

    result.assert_succeeded()
    assert result.next_state == "Complete"
```

## チュートリアル

実データと実ファイルで plugin の使い方を試したい場合は [`tutorials/order_status/`](tutorials/order_status/README.md) を使ってください。

- `tutorials/order_status/tests/test_local_order_flow.py`
  - Step Functions Local に同梱 workflow を流し、成功系と失敗系を確認します
- `tutorials/order_status/tests/test_teststate_order_status.py`
  - 同じ workflow の `CheckStatus` state を AWS `TestState` で直接検証します

手動実行コマンド:

```bash
uv run pytest tutorials/order_status/tests/test_local_order_flow.py -q
uv run pytest tutorials/order_status/tests/test_teststate_order_status.py -q --sfn-role-arn arn:aws:iam::123456789012:role/StepFunctionsTestRole
```

このチュートリアルは学習用資材です。通常の `uv run ci` には含めません。

実 backend を使う自動統合確認は `tests/integration/test_local_backend.py`、`tests/integration/test_teststate_backend.py`、`tests/integration/test_aws_backend.py` にあります。

Step Functions Local を使う場合は、ローカルを起動したうえで次を実行します。

```bash
PYTEST_STEPFUNCTIONS_RUN_LOCAL_INTEGRATION=1 uv run pytest tests/integration/test_local_backend.py -q
```

AWS `TestState` を使う場合は、AWS credentials を用意し、`states:TestState` を使える role ARN を指定して次を実行します。

```bash
PYTEST_STEPFUNCTIONS_RUN_TESTSTATE_INTEGRATION=1 uv run pytest tests/integration/test_teststate_backend.py -q \
  --sfn-role-arn arn:aws:iam::123456789012:role/StepFunctionsTestRole
```

AWS Step Functions を使う `aws` backend の場合は、AWS credentials を用意し、state machine 実行用 role ARN を指定して次を実行します。

```bash
PYTEST_STEPFUNCTIONS_RUN_AWS_INTEGRATION=1 uv run pytest tests/integration/test_aws_backend.py -q \
  --sfn-role-arn arn:aws:iam::123456789012:role/StepFunctionsExecutionRole
```

## 現在の公開 API

### dataclass: `Scenario`

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    input: dict[str, Any]
    case: str | None = None
    name: str | None = None
    timeout: int | None = None
```

### dataclass: `ExecutionResult`

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class ExecutionResult:
    status: str
    backend: str
    execution_arn: str | None
    output_json: Any | None
    error: str | None
    cause: str | None
    next_state: str | None
    raw: dict[str, Any]

    def assert_status(self, expected: str) -> None: ...
    def assert_succeeded(self) -> None: ...
    def assert_failed(self, error: str | None = None) -> None: ...
```

### marker

```python
@pytest.mark.sfn(
    definition="tests/workflows/order_flow.asl.json",
    name="OrderFlow",
    backend="auto",
    timeout=30,
)
```

### fixture

- `sfn_run(scenario, *, definition=None, name=None, backend=None, timeout=None, validate=None, region=None, local_endpoint=None, role_arn=None, definition_root=None, mock_config=None)`
- `sfn_test_state(*, definition=None, state_name, input, backend=None, timeout=None, validate=None, region=None, local_endpoint=None, role_arn=None, definition_root=None, mock_config=None)`

### CLI / `pyproject.toml`

- `--sfn-backend` / `sfn_backend`
- `--sfn-region` / `sfn_region`
- `--sfn-local-endpoint` / `sfn_local_endpoint`
- `--sfn-role-arn` / `sfn_role_arn`
- `--sfn-definition-root` / `sfn_definition_root`
- `--sfn-mock-config` / `sfn_mock_config`
- `--sfn-validate` / `sfn_validate`

`pyproject.toml` 例:

```toml
[tool.pytest.ini_options]
sfn_backend = "auto"
sfn_region = "ap-northeast-1"
sfn_definition_root = "tests/workflows"
sfn_local_endpoint = "http://127.0.0.1:8083"
sfn_role_arn = "arn:aws:iam::123456789012:role/StepFunctionsTestRole"
sfn_mock_config = "tests/stepfunctions/MockConfigFile.json"
sfn_validate = true
markers = [
  "sfn(definition, name=None, backend=None, timeout=None): Step Functions test metadata",
]
```

## backend 方針

### `local`

Step Functions Local を使って state machine 全体を実行します。  
`sfn_run` の既定 backend です。

### `teststate`

AWS `TestState` API を使って state 単体テストを実行します。  
`sfn_test_state` の既定 backend です。
inspection level は alpha では `INFO` 固定で、公開オプションにはしていません。

### `aws`

AWS Step Functions 上で state machine 全体を実行します。  
`sfn_run` でのみ使えます。state machine はテストごとに一時作成し、実行後に削除します。

## alpha 時点のサポート境界

| capability | `local` | `teststate` | `aws` |
| --- | --- | --- | --- |
| `sfn_run` | yes | no | yes |
| `sfn_test_state` | no | yes | no |
| `Scenario.case` | yes | n/a | no |
| `sfn_mock_config` | yes | no | no |
| 常設 CI | local integration のみ | opt-in のみ | opt-in のみ |

## 制約と注意点

- `local` backend は Step Functions Local が別途起動済みである前提です。
- `local` backend で `sfn_mock_config` を指定した場合は、実行前に JSON 構造を検査します。`Scenario.case` を併用した場合だけ test case 名の存在確認も行います。
- `local` backend の validation は AWS `ValidateStateMachineDefinition` を使います。`--sfn-validate` を有効にする場合は AWS API に到達できる認証情報と region が必要です。
- `teststate` backend は `role_arn` が必須です。
- `teststate` backend の opt-in integration test は `PYTEST_STEPFUNCTIONS_RUN_TESTSTATE_INTEGRATION=1` と `--sfn-role-arn` 付きで `tests/integration/test_teststate_backend.py` を実行します。
- `teststate` backend の inspection level は `INFO` 固定です。
- `teststate` backend に対する plugin 内スロットリングはまだ入っていません。`xdist` 併用も alpha では未サポートです。
- `aws` backend は `role_arn` が必須です。
- `aws` backend は `sfn_run` 専用です。`sfn_test_state` では使えません。
- `aws` backend では `Scenario.case`、`sfn_mock_config`、`--sfn-local-endpoint` は使えません。
- `aws` backend の opt-in integration test は `PYTEST_STEPFUNCTIONS_RUN_AWS_INTEGRATION=1` と `--sfn-role-arn` 付きで `tests/integration/test_aws_backend.py` を実行します。
- `aws` backend で `--sfn-validate` を使う場合も AWS `ValidateStateMachineDefinition` を呼ぶ認証情報が必要です。
- `aws` backend の最小権限は `states:CreateStateMachine`、`states:StartExecution`、`states:DescribeExecution`、`states:DeleteStateMachine`、`states:StopExecution`、`iam:PassRole` です。
- `definition` の YAML は未対応です。
- `tutorials/order_status/` は手動チュートリアルであり、integration test の代替ではありません。

## troubleshooting

### `local`

- `--sfn-local-endpoint` の先に Step Functions Local が起動していることを確認してください。
- `sfn_mock_config` を使う場合は root object、`StateMachines`、各 `TestCases` が JSON object になっている必要があります。
- `Scenario.case` と mock config の case 名が一致しない場合は実行前に失敗します。

### `teststate`

- `--sfn-role-arn` または `sfn_role_arn` が必須です。
- `states:TestState` を使える認証情報が必要です。
- 1 TPS 制約があるため、並列実行や `xdist` 併用ではスロットリングしやすくなります。

### `aws`

- `--sfn-role-arn` または `sfn_role_arn` が必須です。
- `sfn_test_state` は使えません。state 単体テストは `teststate` backend を使ってください。
- `Scenario.case`、`sfn_mock_config`、`--sfn-local-endpoint` を渡すと設定エラーになります。

## 開発コマンド

```bash
uv run ci
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run python -m build
```

`uv run ci` は提出前の正本コマンドです。format、lint、type check、coverage 付き test、build、dead code check、dependency audit を順に実行します。
