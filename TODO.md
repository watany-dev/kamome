# TODO

## 0. 方針の固定

- [x] パッケージ名を `pytest-stepfunctions` で確定する
- [x] import 名を `pytest_stepfunctions` で確定する
- [x] v0.1 のスコープを「開発環境 + 最小 plugin scaffold」で固定する
- [x] `aws` backend は v0.1 では stub のみと決める
- [x] Python 対応バージョンを 3.10-3.13 に決める
- [x] boto3 / pytest の最低対応バージョンを `boto3>=1.34` / `pytest>=8.0` に決める

## 1. プロジェクト雛形

- [x] `pyproject.toml` を作成する
- [x] `src/pytest_stepfunctions/` レイアウトにする
- [x] `pytest11` entry point を設定する
- [x] `Framework :: Pytest` classifier を付ける
- [x] formatter / linter / type checker を `ruff` / `mypy` に決める
- [x] CI の最小構成を作る

想定構成:

```text
src/
  pytest_stepfunctions/
    __init__.py
    plugin.py
    model.py
    markers.py
    validation.py
    config.py
    exceptions.py
    backends/
      __init__.py
      base.py
      local.py
      teststate.py
      aws.py
    helpers/
      __init__.py
      assertions.py
tests/
  unit/
  integration/
```

## 2. 公開モデルの実装

### 2.1 `Scenario`

- [x] `Scenario` dataclass を実装する
- [x] `id`
- [x] `input`
- [x] `case`
- [x] `name`
- [x] `timeout`
- [ ] 将来拡張用に metadata の必要性を検討する

### 2.2 `ExecutionResult`

- [x] `ExecutionResult` dataclass を実装する
- [x] `status`
- [x] `backend`
- [x] `execution_arn`
- [x] `output_json`
- [x] `error`
- [x] `cause`
- [x] `next_state`
- [x] `raw`
- [x] `assert_status()` を実装する
- [x] `assert_succeeded()` を実装する
- [x] `assert_failed()` を実装する

### 2.3 spec 用 dataclass

- [ ] `ExecutionSpec` を内部モデルとして作る
- [ ] `StateTestSpec` を内部モデルとして作る
- [ ] `ValidationResult` を内部モデルとして作る
- [ ] diagnostics 表現モデルを作る

## 3. 設定解決レイヤ

- [ ] `pyproject.toml` から設定を読む
- [x] CLI オプションを追加する
- [ ] marker から設定を読む
- [ ] fixture 呼び出し引数で上書きできるようにする
- [ ] 設定優先順位を実装する

優先順位:

1. fixture 呼び出し引数
2. marker
3. CLI
4. `pyproject.toml`
5. デフォルト値

### CLI 候補

- [ ] `--sfn-backend`
- [ ] `--sfn-region`
- [ ] `--sfn-local-endpoint`
- [ ] `--sfn-role-arn`
- [ ] `--sfn-definition-root`
- [ ] `--sfn-mock-config`
- [ ] `--sfn-validate`

## 4. pytest plugin 本体

### 4.1 marker 登録

- [x] `pytest_configure()` を実装する
- [x] `sfn` marker を登録する
- [x] `pytest --markers` で説明が見えるようにする

### 4.2 option 登録

- [x] `pytest_addoption()` を実装する
- [x] backend に choices を付ける
- [ ] 不正値時の usage error を確認する

### 4.3 fixture 実装

- [x] `sfn_run` fixture を作る
- [x] `sfn_test_state` fixture を作る
- [ ] 必要なら `sfn_validate` fixture を作る
- [ ] session-scoped client fixture を作る
- [ ] function-scoped executor fixture を作る
- [ ] fixture の未実装 stub を本実装に置き換える

### 4.4 assertion rewriting

- [x] helper モジュールを `register_assert_rewrite()` 対象にする
- [ ] 失敗時メッセージの見え方を確認する

## 5. 定義ロードと正規化

- [ ] `definition` がファイルパスならロードする
- [ ] `definition` が `dict` ならそのまま受ける
- [ ] `definition` が JSON 文字列なら parse する
- [ ] 無効な JSON のエラーをわかりやすくする
- [ ] YAML を v0.1 で入れるか決める
- [ ] state machine 名のデフォルト解決規則を決める

## 6. backend 抽象化

### 6.1 base

- [ ] `Backend` Protocol または abstract base class を作る
- [ ] `validate()`
- [ ] `run()`
- [ ] `test_state()`
- [ ] backend 名の取得方法を定義する

### 6.2 auto 解決

- [ ] `backend="auto"` の解決ロジックを実装する
- [ ] `state_name` があるときは `teststate`
- [ ] `case` があり Local endpoint があるときは `local`
- [ ] それ以外は `local` 優先
- [ ] 解決不能時のエラーを実装する

## 7. validation 実装

- [ ] `ValidateStateMachineDefinition` 呼び出しを実装する
- [ ] diagnostics を内部モデルへ変換する
- [ ] `result == "FAIL"` のときの表示を整える
- [ ] diagnostics 文言に依存しすぎない実装にする
- [ ] `sfn_run` 実行前に optional で validation する流れを作る

## 8. `local` backend 実装

### 8.1 クライアント生成

- [ ] Step Functions Local endpoint 用クライアントを作る
- [ ] credentials のダミー注入方針を決める
- [ ] region の扱いを固定する

### 8.2 state machine lifecycle

- [ ] CreateStateMachine を実装する
- [ ] 既存名衝突時の扱いを決める
- [ ] テスト後 DeleteStateMachine を実装する
- [ ] 実行名の生成規則を決める

### 8.3 execution

- [ ] `Scenario.case` を `stateMachineArn#CaseName` に変換する
- [ ] StartExecution を実装する
- [ ] DescribeExecution で完了待ちする
- [ ] timeout 超過時の失敗を実装する
- [ ] `ExecutionResult` への変換を実装する

### 8.4 mock config 連携

- [ ] `sfn_mock_config` 設定を読む
- [ ] case 未定義時のエラーをわかりやすくする
- [ ] mock config の軽い事前検証を入れる
- [ ] `StateMachines -> TestCases -> MockedResponses` 構造の検証を入れる
- [ ] `MockedResponses` の key 重複や欠損のチェックを検討する

### 8.5 Local 特有の注意点

- [ ] feature parity なしの注意を README に書く
- [ ] Map の挙動差分に関する注意を README に書く
- [ ] mock が AWS 実 API と一致保証されない点を書く

## 9. `teststate` backend 実装

### 9.1 リクエスト構築

- [ ] 単一 state 定義を受ける
- [ ] 完全定義 + `state_name` を受ける
- [ ] `input` を JSON に正規化する
- [ ] inspection level の扱いを決める

### 9.2 実行

- [ ] `test_state` API 呼び出しを実装する
- [ ] `ExecutionResult` への変換を実装する
- [ ] `next_state` の取り扱いを実装する
- [ ] エラー時の正規化を実装する

### 9.3 quota 対策

- [ ] 1 TPS 制約を README に書く
- [ ] plugin 側で簡易スロットリングするか決める
- [ ] 並列実行時の警告を出すか決める
- [ ] xdist との相性を README に書く

## 10. `aws` backend の扱い

- [ ] v0.1 で stub のみ置くか決める
- [ ] v0.2 のロードマップとして README に書く
- [ ] もし入れるなら Create/Start/Describe/Delete の流れを実装する
- [ ] role ARN 必須条件を整理する

## 11. エラーモデル

- [ ] `ConfigurationError` を作る
- [ ] `BackendResolutionError` を作る
- [ ] `DefinitionLoadError` を作る
- [ ] `ValidationError` を作る
- [ ] `ExecutionTimeoutError` を作る
- [ ] `MockCaseNotFoundError` を作る
- [ ] boto3 例外を包む変換層を作る

## 12. ユーザー向けメッセージ改善

- [ ] state 名を含む失敗メッセージにする
- [ ] definition ファイルパスを含む失敗メッセージにする
- [ ] AWS 認証不足時のメッセージを改善する
- [ ] Local endpoint 未起動時のメッセージを改善する
- [ ] case 名 typo 時の候補表示を検討する

## 13. テスト実装

### 13.1 unit test

- [ ] 設定優先順位のテスト
- [ ] marker 読み取りのテスト
- [ ] definition ロードのテスト
- [ ] backend auto 解決のテスト
- [x] `ExecutionResult` のテスト
- [ ] 例外変換のテスト

### 13.2 plugin test

- [x] `pytester` を使った plugin 読み込みテスト
- [x] marker 登録テスト
- [x] fixture 解決テスト
- [x] CLI オプション反映テスト
- [x] `pytest --markers` 表示テスト

### 13.3 integration test

- [ ] Step Functions Local を使った integration test
- [ ] HappyPath 実行テスト
- [ ] failure case 実行テスト
- [ ] timeout テスト
- [ ] mock case 切り替えテスト

### 13.4 AWS integration test

- [ ] `TestState` 呼び出しテスト
- [ ] Choice state の分岐確認
- [ ] Fail state の確認
- [ ] API 制限回避のため serial 実行設定を入れる

## 14. CI

- [x] GitHub Actions を作る
- [x] lint ジョブを追加する
- [x] unit test ジョブを追加する
- [x] plugin test ジョブを追加する
- [ ] Step Functions Local integration job を追加する
- [ ] 必要なら AWS `TestState` job を分離する

### CI でやること

- [x] build
- [ ] validation
- [ ] local backend test
- [ ] optional な teststate backend test

## 15. ドキュメント

### 15.1 README

- [x] 目的を書く
- [x] backend の違いを書く
- [x] Quick Start を入れる
- [x] 設定例を書く
- [x] CI での使い分けを書く
- [x] 制約事項を書く
- [ ] 非目標を書く

### 15.2 docs

- [ ] API reference を作る
- [x] 開発環境設計書を作る
- [x] 要件メモを作る
- [ ] backend ごとの詳細を書く
- [ ] Local mock config の考え方を書く
- [ ] `TestState` を使う場面を書く
- [ ] トラブルシュートを書く

### 15.3 examples

- [ ] 最小構成 example
- [ ] Local mock example
- [ ] `TestState` example
- [ ] GitHub Actions example

## 16. リリース準備

- [ ] package metadata を埋める
- [ ] versioning 方針を決める
- [ ] changelog を作る
- [ ] license を決める
- [ ] PyPI 公開手順を整える
- [ ] 初回リリースチェックリストを作る

## 17. v0.1 の完了条件

- [ ] plugin が `pytest -p pytest_stepfunctions.plugin` なしで読み込まれる
- [ ] `@pytest.mark.sfn` が使える
- [ ] `sfn_run` が使える
- [ ] `sfn_test_state` が使える
- [ ] `Scenario` と `ExecutionResult` が安定する
- [ ] `local` backend が integration test で動く
- [ ] `teststate` backend が最小ケースで動く
- [ ] README の Quick Start がそのまま動く
- [ ] CI が green になる

## 18. 後続候補

- [ ] `aws` backend を正式実装する
- [ ] JUnit XML への詳細出力を検討する
- [ ] richer assertion helper を追加する
- [ ] YAML definition 対応を追加する
- [ ] Local mock config の lint 機能を検討する
- [ ] state machine 定義のキャッシュ戦略を検討する
- [ ] xdist 連携方針を整理する
