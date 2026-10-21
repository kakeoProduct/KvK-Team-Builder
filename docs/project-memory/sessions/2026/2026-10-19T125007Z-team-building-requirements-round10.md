---
type: session
id: 2026-10-19T125007Z-team-building-requirements-round10
title: 休止を最上位の指標で避け、序盤はリーダー不在でも出撃させる
status: current
created_at: '2026-10-19T12:50:07Z'
base_commit: 3e929ad4e6269dbda390687fad367d683c2e480e
final_commit: 3e929ad4e6269dbda390687fad367d683c2e480e
tags:
- requirements
- team-building
related_paths:
- docs/requirements/team-building/README.md
- docs/requirements/team-building/formation-rules.md
- docs/requirements/team-building/open-questions.md
- docs/requirements/team-building/output-and-screen.md
- tests/test_repository_scope.py
---

# 休止を最上位の指標で避け、序盤はリーダー不在でも出撃させる

## 利用者の依頼

PR #43の7回目の再レビューのMust、Shouldと確認事項1件の回答を要件へ反映する

## 実装結果

旧Q-090を記録した。休止の数を目的関数の最上位（⓪）に置き、時間帯を問わず7人の代わりに休止させない。序盤はリーダー不在でも出撃させ、自動で遅れて出撃するのはFIXの隊だけにした。遅れて出撃させる案を（隊、時間帯）ごとに判定し、⑩の数え方、隊数を減らす範囲、Validatorとアプリケーションの責務、FRM-040の古い除外、画面の表示、分割案の重なりを直した。作成者の仮定A-12を加え、取り下げた仮定への参照を構造テストで検出する

## 重要な判断

- 序盤はリーダーがいなくても隊を作成する（旧Q-090）
- 休止の数を目的関数の最上位に置く（旧Q-087の反映）

## 検証

- python tools/check.py 成功（116 passed）
- 取り下げた仮定への参照を構造テストが検出することを一時コピーで確認

## 未完了事項

- 対応後の再レビュー

## 正本への参照

- `docs/requirements/team-building/README.md`
- `docs/requirements/team-building/formation-rules.md`
- `docs/requirements/team-building/open-questions.md`
- `docs/requirements/team-building/output-and-screen.md`
- `tests/test_repository_scope.py`
