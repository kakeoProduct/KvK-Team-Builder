---
type: session
id: 2026-07-22T144313Z-shared-dev-container-extensions
title: Dev Container間でVS Code拡張機能を共有
status: current
created_at: '2026-07-22T14:43:13Z'
base_commit: 8608087429e73f738faad44633f5636f96030b79
final_commit: 8608087429e73f738faad44633f5636f96030b79
tags:
- codex
- development
- docker
- vscode
related_paths:
- .devcontainer/devcontainer.json
- DEVELOPMENT.md
- docs/adr/0011-share-vscode-extensions-between-dev-containers.md
- docs/adr/README.md
- tests/test_dev_container.py
---

# Dev Container間でVS Code拡張機能を共有

## 利用者の依頼

必要なVS Code拡張機能をDev Container間で共有し、Codexも含める

## 実装結果

Codex、Python、Pylance、Ruffを自動導入し、拡張機能だけを名前付きDocker volumeで再利用する構成を追加した

## 重要な判断

- OpenAI.chatgptを拡張機能へ含めるが、Codexのログイン状態、VS Code Server全体、Docker socket、認証情報は共有しない

## 検証

- git diff --check: 成功; python -m pytest tests/test_dev_container.py -q: 2 passed; python tools/check.py: Ruff、mypy、pytest 36件成功

## 未完了事項

- WindowsのDocker DesktopでContainer再作成時の拡張機能再利用を確認予定

## 正本への参照

- `.devcontainer/devcontainer.json`
- `DEVELOPMENT.md`
- `docs/adr/0011-share-vscode-extensions-between-dev-containers.md`
- `docs/adr/README.md`
- `tests/test_dev_container.py`
