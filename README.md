# pytest-stepfunctions

`pytest-stepfunctions` は、AWS Step Functions を `pytest` からテストするためのプラグインです。

主な目的は、次の 3 つです。

- ASL 定義の壊れを早く検知する
- 分岐、retry、catch を CI 上で再現可能にする
- Step Functions Local と AWS `TestState` を使い分けられるようにする

このプラグインは、pytest の流儀に合わせて、fixture と marker を中心に API を設計します。

## 何が嬉しいか

Step Functions のテストは、Lambda 単体テストだけでは足りません。実際に壊れやすいのは、次のような部分です。

- Choice の分岐条件
- Retry / Catch の条件
- ResultPath / OutputPath の組み合わせ
- 失敗時のエラー名や Cause の扱い
- Local と AWS 実解釈の差

`pytest-stepfunctions` は、これらを次のレイヤで検証できるようにします。

- `ValidateStateMachineDefinition` による構文検証
- Step Functions Local による高速回帰テスト
- AWS `TestState` による state 単体テスト

## 設計方針

公開 API はできるだけ pytest 標準に寄せます。

- 実行 API は fixture にする
- 静的設定は marker にする
- 複数シナリオは `@pytest.mark.parametrize` で表現する
- 戻り値は boto3 生レスポンスではなく共通 dataclass に揃える
- backend 差分は `local` / `teststate` / `aws` で抽象化する

## インストール

```bash
pip install pytest-stepfunctions
```

## 基本コンセプト

このプラグインは、少なくとも次の 3 種類の backend を想定します。

### `local`

Step Functions Local を使って state machine 全体を実行します。  
CI での高速回帰向けです。

### `teststate`

AWS `TestState` API を使って state 単体テストを行います。  
壊れやすい Choice / Task / Fail 遷移の確認向けです。

### `aws`

実際に state machine を作成・実行して確認する backend です。  
初期版では optional 扱いを想定しています。

## クイックスタート

### 1. state machine 実行テスト

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

この形にしている理由は単純です。  
分岐ごとにテスト関数を増やすのではなく、`Scenario` を `parametrize` で展開したほうが、state machine のケース追加とテスト追加が 1 対 1 で対応するからです。

### 2. state 単体テスト

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

この API を `sfn_run` と分けているのは、state machine 全体の実行テストと、state 単体のロジックテストは責務が違うからです。

## 公開 API

### marker

```python
@pytest.mark.sfn(
    definition="tests/workflows/order_flow.asl.json",
    name="OrderFlow",
    backend="auto",
    timeout=30,
)
```

#### 引数

- `definition`: ASL 定義。ファイルパス、`dict`、JSON 文字列を受け付ける
- `name`: state machine 名
- `backend`: `auto | local | teststate | aws`
- `timeout`: 実行待ちタイムアウト秒数

### fixture: `sfn_run`

state machine 全体を実行する fixture です。  
返り値は callable で、`Scenario` を受け取って `ExecutionResult` を返します。

### fixture: `sfn_test_state`

state 単体テスト用 fixture です。  
`definition`、`state_name`、`input` を受け取って `ExecutionResult` を返します。

### dataclass: `Scenario`

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class Scenario:
    id: str
    input: dict[str, Any]
    case: str | None = None
    name: str | None = None
    timeout: int | None = None
```

- `id`: pytest 上の表示名
- `input`: execution input
- `case`: Step Functions Local の test case 名
- `name`: execution 名の上書き
- `timeout`: 個別タイムアウト

### dataclass: `ExecutionResult`

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
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

共通戻り値を用意する理由は、backend ごとの差分をユーザーのテストコードに漏らさないためです。

## 設定

`pyproject.toml` で共通設定できます。

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

## CLI オプション

```bash
pytest \
  --sfn-backend=local \
  --sfn-region=ap-northeast-1 \
  --sfn-local-endpoint=http://127.0.0.1:8083
```

想定オプションは次です。

- `--sfn-backend`
- `--sfn-region`
- `--sfn-local-endpoint`
- `--sfn-role-arn`
- `--sfn-definition-root`
- `--sfn-validate`

## backend 解決

`backend="auto"` のときは、次の順で解決します。

- `state_name` があるなら `teststate`
- `case` があり Local endpoint が設定済みなら `local`
- それ以外は `local` を優先
- 必要な AWS 認証情報がなければ usage error にする

## CI での使い分け

おすすめは次の 3 層です。

### 1. 定義検証

ASL の構文だけを確認します。  
state machine を作らずに壊れを検知できます。

### 2. Step Functions Local

分岐、retry、catch などの execution path を高速に確認します。  
CI のメイン回帰テスト向けです。

### 3. AWS `TestState`

壊れやすい state だけ AWS 側で直列実行します。  
Choice や Task の境界条件確認に向いています。

## 失敗時の考え方

このプラグインは、壊れた場所を切り分けやすくすることを重視します。

- validation で落ちる  
  → ASL 定義そのものの問題

- local で落ちる  
  → 分岐、retry、ResultPath などロジックの問題

- teststate でだけ落ちる  
  → Local と AWS 解釈差、または AWS 側制約の問題

## 非目標

このプラグインは次を主目的にしません。

- ASL を Python DSL で記述すること
- デプロイツールになること
- 本番環境の完全な統合テスト基盤になること
- Step Functions Local の mock JSON を独自 DSL で完全抽象化すること

## 初期リリース範囲

v0.1 では次を提供します。

- `@pytest.mark.sfn`
- `Scenario`
- `ExecutionResult`
- `sfn_run`
- `sfn_test_state`
- `local` backend
- `teststate` backend
- validation 呼び出し
- CLI / `pyproject.toml` 設定
- pytest plugin 自動登録

`aws` backend は後続バージョンで追加予定です。

## ライセンス

TBD
