# TODO

## 0. 固定済み方針

- [x] パッケージ名を `pytest-stepfunctions` で固定する
- [x] import 名を `pytest_stepfunctions` で固定する
- [x] Python 対応を 3.10-3.13 に固定する
- [x] 開発ワークフローを `uv` に固定する
- [x] `aws` backend は当面 stub 扱いにする

## 1. 基盤と公開 API

- [x] `pytest11` entry point を有効にする
- [x] `sfn` marker を登録する
- [x] `--sfn-*` CLI オプションを登録する
- [x] `pyproject.toml` から `sfn_*` 設定を読む
- [x] `Scenario` を公開する
- [x] `ExecutionResult` を公開する
- [x] assertion helper を公開 API として整える

## 2. core runtime

- [x] `ExecutionSpec` を内部モデルとして実装する
- [x] `StateTestSpec` を内部モデルとして実装する
- [x] `ValidationResult` を内部モデルとして実装する
- [x] diagnostics 表現モデルを実装する
- [x] `ConfigurationError` を実装する
- [x] `BackendResolutionError` を実装する
- [x] `DefinitionLoadError` を実装する
- [x] `ValidationError` を実装する
- [x] `ExecutionTimeoutError` を実装する
- [x] `MockCaseNotFoundError` を実装する
- [x] boto3 / botocore 例外を包む変換層を入れる
- [x] `definition` の path / `dict` / JSON string 対応を入れる
- [x] invalid JSON のエラーをわかりやすくする
- [x] state machine 名のデフォルト解決規則を入れる
- [x] 設定優先順位を `fixture > marker > CLI > pyproject > default` で実装する
- [x] `backend="auto"` を `sfn_run -> local`, `sfn_test_state -> teststate` で解決する
- [x] optional validation を `ValidateStateMachineDefinition` で実装する

## 3. backend 実装

### 3.1 `local`

- [x] Step Functions Local endpoint 用クライアントを作る
- [x] dummy credentials を注入する
- [x] region を設定から解決する
- [x] CreateStateMachine / StartExecution / DescribeExecution / DeleteStateMachine を実装する
- [x] execution timeout を実装する
- [x] `Scenario.case` を `stateMachineArn#CaseName` に変換する
- [x] `ExecutionResult` への変換を実装する
- [x] `sfn_mock_config` を読んで test case 存在確認を入れる
- [ ] mock config の深い構造検証を入れる
- [x] Local integration test を追加する

### 3.2 `teststate`

- [x] `TestState` API 呼び出しを実装する
- [x] `role_arn` 必須条件を実装する
- [x] `ExecutionResult` への変換を実装する
- [x] `next_state` の取り扱いを実装する
- [x] backend エラーの正規化を実装する
- [ ] 単一 state 定義の専用入力形を整理する
- [ ] inspection level の公開方針を決める
- [ ] 1 TPS 制約への対策を入れるか決める

### 3.3 `aws`

- [x] 未実装 stub を残す
- [ ] 正式実装のマイルストーンを設計する

## 4. fixture と plugin の残タスク

- [x] `sfn_run` fixture を本実装へ置き換える
- [x] `sfn_test_state` fixture を本実装へ置き換える
- [x] marker 読み取りを実装する
- [x] fixture override を実装する
- [ ] `sfn_validate` fixture を追加するか決める
- [ ] session-scoped client fixture を導入するか決める

## 5. テスト

- [x] definition ロードの unit test
- [x] 設定優先順位の unit test
- [x] marker 読み取りの unit test
- [x] backend auto 解決の unit test
- [x] backend error / validation / timeout の unit test
- [x] `pytester` を使う plugin test
- [x] 95% 以上の branch coverage を維持する
- [x] Step Functions Local integration test
- [ ] AWS `TestState` の opt-in integration test

## 6. ドキュメント

- [x] README を runtime 実装後の内容へ更新する
- [x] `docs/requirements.md` を runtime 実装後のスコープへ更新する
- [x] runtime backend 設計書を追加する
- [x] `tutorials/order_status/` に手動チュートリアルを追加する
- [ ] backend ごとの troubleshooting を追加する
- [x] examples を追加する
- [x] GitHub Actions で Local integration job を追加する

## 7. 後続候補

- [ ] `Scenario` の metadata 拡張を検討する
- [ ] YAML definition 対応を追加する
- [ ] mock config lint を追加する
- [ ] `aws` backend を正式実装する
- [ ] xdist 連携方針を整理する
- [ ] release / changelog / PyPI 手順を整える
