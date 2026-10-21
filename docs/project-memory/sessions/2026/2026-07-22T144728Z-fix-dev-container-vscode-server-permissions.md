---
type: session
id: 2026-07-22T144728Z-fix-dev-container-vscode-server-permissions
title: Dev ContainerのVS Code Server権限を修正
status: current
created_at: '2026-07-22T14:47:28Z'
base_commit: 6648edfaa3bbeb01b939c40401095f93a4cdf298
final_commit: 6648edfaa3bbeb01b939c40401095f93a4cdf298
tags:
- bugfix
- development
- docker
- vscode
related_paths:
- .devcontainer/Dockerfile
- tests/test_dev_container.py
---

# Dev ContainerのVS Code Server権限を修正

## 利用者の依頼

Dev Container起動時のvscode-server bin作成権限エラーを修正する

## 実装結果

Dockerfileでvscode所有のVS Code Serverディレクトリをvolume mount前に作成し、回帰テストを追加した

## 重要な判断

- 共有extension volumeの親とbinをimage内で非root利用者へ所有させ、VS Code Serverの起動前処理を妨げない

## 検証

- git diff --check: 成功; python -m pytest tests/test_dev_container.py -q: 2 passed; python tools/check.py --fix: Ruff、mypy、pytest 36件成功

## 未完了事項

- WindowsのDocker DesktopでContainer再作成を確認予定

## 正本への参照

- `.devcontainer/Dockerfile`
- `tests/test_dev_container.py`
