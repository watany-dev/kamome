# order_status tutorial

`pytest-stepfunctions` の現在実装を、実際の ASL 定義と入力データで試すための手動チュートリアルです。

このチュートリアルでは次の 2 つを体験できます。

- `sfn_run` で state machine 全体を Step Functions Local に流す
- `sfn_test_state` で同じ定義の `CheckStatus` state を AWS `TestState` で単体検証する

どちらも同じ定義ファイルと入力 JSON を使います。

## ファイル構成

```text
tutorials/order_status/
  README.md
  inputs/
    paid.json
    pending.json
  tests/
    test_local_order_flow.py
    test_teststate_order_status.py
  workflows/
    order_status.asl.json
```

## シナリオ

state machine は注文ステータスを見て次へ進むだけの最小構成です。

- `paid.json`
  - `status` が `PAID`
  - full workflow では `SUCCEEDED`
  - `TestState` では `next_state == "Complete"`
- `pending.json`
  - `status` が `PENDING`
  - full workflow では `FAILED` with `Order.NotPaid`
  - `TestState` では `next_state == "Reject"`

## 前提

### 共通

- repository root で `uv sync --extra dev` 済み
- コマンドは `/workspaces/kamome` で実行する

### `sfn_run` / Step Functions Local

- Step Functions Local が `http://127.0.0.1:8083` で起動済み

例:

```bash
docker run --rm -p 8083:8083 amazon/aws-stepfunctions-local
```

### `sfn_test_state` / AWS TestState

- AWS credentials が設定済み
- `states:TestState` を使える role ARN を指定できる

## 実行

### 1. workflow 全体を Local で流す

```bash
uv run pytest tutorials/order_status/tests/test_local_order_flow.py -q
```

期待結果:

- `paid` が成功する
- `pending` が `Order.NotPaid` で失敗する

### 2. `CheckStatus` を TestState で単体検証する

```bash
uv run pytest tutorials/order_status/tests/test_teststate_order_status.py -q \
  --sfn-role-arn arn:aws:iam::123456789012:role/StepFunctionsTestRole
```

期待結果:

- `paid` が `Complete` を返す
- `pending` が `Reject` を返す

## 注意

- このフォルダは学習用の手動チュートリアルです。通常の `uv run ci` では実行しません。
- `aws` backend はまだ未実装なので、このチュートリアルでも扱いません。
- `--sfn-validate` を付けると AWS `ValidateStateMachineDefinition` を使うため、Local 実行でも AWS 認証が必要になります。
