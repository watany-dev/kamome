# Changelog

このファイルは Keep a Changelog 形式をベースに管理する。

## [Unreleased]

- 変更なし

## [0.1.0a1] - 2026-03-10

### Added

- `local` backend で `sfn_mock_config` の JSON 構造検査を追加
- backend ごとの troubleshooting を README に追加
- maintainer 向け release 手順書 `docs/release.md` を追加
- tag 起点の PyPI publish workflow を追加

### Changed

- Public PyPI alpha のサポート境界を README / requirements / design docs に明記
- `teststate` backend の inspection level を alpha では `INFO` 固定と明記
- `aws` backend の `sfn_test_state` 非対応を alpha の仕様として固定
