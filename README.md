# pytest-stepfunctions

`pytest-stepfunctions` は、AWS Step Functions を `pytest` からテストするための pytest plugin です。

このリポジトリでは、次の 3 つを主な目的にしています。

- ASL 定義の壊れを早く検知する
- 分岐、retry、catch を CI 上で再現可能にする
- Step Functions Local と AWS `TestState` を使い分けられるようにする

## 現在のステータス

このリポジトリは、実行 backend 実装の前段階として開発環境と plugin 骨組みを持つ状態です。

現時点で実装済みのもの:

- `pyproject.toml` と `src/pytest_stepfunctions/` レイアウト
- `pytest11` entry point による plugin 自動読込設定
- `sfn` marker の登録
- `--sfn-*` CLI オプションの登録
- `Scenario` と `ExecutionResult` の公開 dataclass
- `sfn_run` と `sfn_test_state` fixture の scaffold
- `ruff`、`mypy`、`pytest`、`build` を使う最小 CI

まだ未実装のもの:

- ASL definition のロードと正規化
- `local` backend の state machine 実行
- `teststate` backend の `TestState` 実行
- validation 実行と設定優先順位の解決
- Step Functions Local を使う integration test

`sfn_run` と `sfn_test_state` は名前解決できますが、現時点では呼び出すと「scaffold 済みだが未実装」で明示的に失敗します。

## 設計方針

公開 API はできるだけ pytest 標準に寄せます。

- 実行 API は fixture にする
- 静的設定は marker にする
- 複数シナリオは `@pytest.mark.parametrize` で表現する
- 戻り値は boto3 生レスポンスではなく共通 dataclass に揃える
- backend 差分は `local` / `teststate` / `aws` で抽象化する

v0.1 で固定した方針:

- パッケージ名は `pytest-stepfunctions`
- import 名は `pytest_stepfunctions`
- Python 対応は 3.10 から 3.13
- 開発ワークフローは `uv`
- 初回 CI は lint、type check、unit/plugin tests、build のみ
- `aws` backend は v0.1 では stub のみ

## インストール

利用者向けの最終形は次を想定しています。

```bash
pip install pytest-stepfunctions
```

ただし、現時点では PyPI 公開前の scaffold 段階です。開発参加時は `uv` を使います。

```bash
uv sync --extra dev
```

## 開発コマンド

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run python -m build
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

- `sfn_run`
- `sfn_test_state`

### CLI

- `--sfn-backend`
- `--sfn-region`
- `--sfn-local-endpoint`
- `--sfn-role-arn`
- `--sfn-definition-root`
- `--sfn-mock-config`
- `--sfn-validate`

## 予定している API 例

以下は最終形の利用イメージであり、まだ動作しません。

### state machine 実行テスト

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
        assert result.output_json == {"orderId": "o-1", "status": "paid"}
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
    )

    result.assert_succeeded()
    assert result.next_state == "Complete"
```

## backend 方針

### `local`

Step Functions Local を使って state machine 全体を実行する想定です。  
CI での高速回帰向けで、v0.1 の主対象です。

### `teststate`

AWS `TestState` API を使って state 単体テストを行う想定です。  
Choice / Task / Fail 遷移の確認向けで、v0.1 の主対象です。

### `aws`

実 state machine を AWS 上に作成して確認する backend です。  
v0.1 では名前だけを残す stub 扱いで、実装と CI 対象には含めません。

## 設定方針

最終的な設定優先順位は次を予定しています。

1. fixture 呼び出し引数
2. marker
3. CLI
4. `pyproject.toml`
5. デフォルト値

`pyproject.toml` の設定例:

```toml
[tool.pytest.ini_options]
sfn_backend = "auto"
sfn_region = "ap-northeast-1"
sfn_definition_root = "tests/workflows"
sfn_local_endpoint = "http://127.0.0.1:8083"
sfn_mock_config = "tests/stepfunctions/MockConfigFile.json"
markers = [
  "sfn(definition, name=None, backend=None, timeout=None): Step Functions test metadata",
]
```

この設定解決はまだ未実装です。

## 制約事項

- Step Functions Local と AWS 実サービスの feature parity は保証しません
- `TestState` の quota や並列実行制約への対応は未実装です
- Step Functions Local 用 Docker 構成と integration test job はまだありません
- README 内の「予定している API 例」は、実装済み機能ではありません

## ドキュメント

- [TODO.md](./TODO.md): 実装バックログ
- [docs/requirements.md](./docs/requirements.md): v0.1 要件メモ
- [docs/design/development-environment.md](./docs/design/development-environment.md): 開発環境 scaffold の設計
