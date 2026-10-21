---
type: session
id: 2026-07-22T143359Z-windows-dev-container
title: Windowsローカル開発用Dev Containerを追加
status: current
created_at: '2026-07-22T14:33:59Z'
base_commit: c58711e7e90b2e0dd15fde8671a8e989cb522703
final_commit: c58711e7e90b2e0dd15fde8671a8e989cb522703
tags:
- ai-harness
- development
- docker
- windows
related_paths:
- .devcontainer/Dockerfile
- .devcontainer/devcontainer.json
- .dockerignore
- .gitattributes
- DEVELOPMENT.md
- README.md
- docs/adr/0010-adopt-dev-container-for-windows-local-development.md
- docs/adr/README.md
- tests/test_dev_container.py
---

# Windowsローカル開発用Dev Containerを追加

## 利用者の依頼

Windowsローカル環境へ移行できる最小Docker Desktop Dev Container構成を作成しpushする

## 実装結果

非rootのPython 3.12 Dev Container、Windows手順、LF統一、ADR、回帰テストを追加した

## 重要な判断

- Docker Compose、利用者向けUbuntu、Docker socket、認証情報注入を含めず、Docker DesktopのWSL 2バックエンドだけを必須とした

## 検証

- git diff --check: 成功; python -m pytest tests/test_dev_container.py -q: 2 passed; python tools/check.py: Ruff、mypy、pytest 36件成功

## 未完了事項

- Docker Desktop実機での初回Container作成は利用者のWindows環境で実施予定

## 正本への参照

- `.devcontainer/Dockerfile`
- `.devcontainer/devcontainer.json`
- `.dockerignore`
- `.gitattributes`
- `DEVELOPMENT.md`
- `README.md`
- `docs/adr/0010-adopt-dev-container-for-windows-local-development.md`
- `docs/adr/README.md`
- `tests/test_dev_container.py`
