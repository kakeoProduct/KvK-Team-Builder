---
type: session
id: 2026-10-17T080534Z-match-workspace-owner
title: Dev Containerで作業ツリーの所有者を実行利用者へそろえる
status: current
created_at: '2026-10-17T08:05:34Z'
base_commit: dc848bb99a0a52c06d283069704617b63604ed66
final_commit: dc848bb99a0a52c06d283069704617b63604ed66
tags:
- dev-container
- git
related_paths:
- .devcontainer/Dockerfile
- .devcontainer/devcontainer.json
- .devcontainer/fix-workspace-owner.sh
- DEVELOPMENT.md
- docs/adr/0016-match-workspace-owner-in-dev-container.md
- docs/adr/README.md
- tests/test_dev_container.py
---

# Dev Containerで作業ツリーの所有者を実行利用者へそろえる

## 利用者の依頼

Repositoryの所有者と実行利用者を一致させる（方式は限定sudoを利用者が選択）

## 実装結果

引数なしの専用Scriptだけをsudoで許可し、postStartCommandで作業ツリーと.gitの所有者をSUDO_UIDへ変更するようにした。ADR 0016とDEVELOPMENT.mdを追加・更新した

## 重要な判断

- safe.directoryの例外ではなく所有者を一致させる。Gitが検査する最上位と.gitだけを非再帰で変更する
- rootのPID 1、Volumeへのclone、手作業での変更は採用しない（ADR 0016）

## 検証

- python tools/check.py: 成功（76 passed）
- chownを差し替えたScriptの擬似実行: 正常時は2パスだけ変更し、sudo情報なし・引数あり・不正UIDを拒否

## 未完了事項

- このContainerではdocker build未実施。Rebuild Container後にgit statusが通ることの確認が必要
- 変更は未コミット。ADR 0016は提案中

## 正本への参照

- `.devcontainer/Dockerfile`
- `.devcontainer/devcontainer.json`
- `.devcontainer/fix-workspace-owner.sh`
- `DEVELOPMENT.md`
- `docs/adr/0016-match-workspace-owner-in-dev-container.md`
- `docs/adr/README.md`
- `tests/test_dev_container.py`
