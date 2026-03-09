# release 手順

この文書は `pytest-stepfunctions` の maintainer が Public PyPI 向け alpha を公開するときの標準手順をまとめる。

## 前提

- PyPI 側で Trusted Publishing を設定済みであること
- GitHub Actions の publish workflow が有効であること
- 公開対象 version が `pyproject.toml` と `CHANGELOG.md` に反映されていること

## リリース前チェック

1. 作業ツリーが意図した変更だけになっていることを確認する
2. `uv sync --extra dev`
3. `uv run ci`
4. 必要なら opt-in integration を追加で実行する
   - `PYTEST_STEPFUNCTIONS_RUN_LOCAL_INTEGRATION=1 uv run pytest tests/integration/test_local_backend.py -q`
   - `PYTEST_STEPFUNCTIONS_RUN_TESTSTATE_INTEGRATION=1 uv run pytest tests/integration/test_teststate_backend.py -q --sfn-role-arn ...`
   - `PYTEST_STEPFUNCTIONS_RUN_AWS_INTEGRATION=1 uv run pytest tests/integration/test_aws_backend.py -q --sfn-role-arn ...`
5. `uv run python -m build`
6. `dist/` に wheel と sdist が生成されていることを確認する

## version と changelog

1. `pyproject.toml` の version を次の公開版に更新する
2. `CHANGELOG.md` に対象 version の項目を追加する
3. README / `TODO.md` / `docs/requirements.md` / `docs/design/runtime-backends.md` の公開境界を確認する

## 公開

1. release commit を作成する
2. `v<version>` の annotated tag を作成する
3. tag を push する
4. GitHub Actions の `Publish` workflow が成功することを確認する
5. PyPI で version と metadata を確認する

## 公開後確認

- `pip install pytest-stepfunctions==<version>` で取得できること
- `pytest --help` に `--sfn-*` オプションが表示されること
- `pytest --markers` に `sfn` marker が表示されること
- changelog と README の version 境界が意図どおりであること
