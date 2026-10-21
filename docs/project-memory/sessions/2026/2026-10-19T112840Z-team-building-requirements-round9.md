---
type: session
id: 2026-10-19T112840Z-team-building-requirements-round9
title: 休止を6人以下と同じく扱い、分かりやすい配置を優先する
status: current
created_at: '2026-10-19T11:28:40Z'
base_commit: d2be791a327d0b606a9cbe4bfb00636037b34cba
final_commit: d2be791a327d0b606a9cbe4bfb00636037b34cba
tags:
- requirements
- team-building
related_paths:
- docs/requirements/team-building/README.md
- docs/requirements/team-building/formation-rules.md
- docs/requirements/team-building/open-questions.md
- docs/requirements/team-building/output-and-screen.md
- docs/requirements/team-building/roster-input.md
- tests/test_repository_scope.py
---

# 休止を6人以下と同じく扱い、分かりやすい配置を優先する

## 利用者の依頼

PR #43の6回目の再レビューのMust、Shouldと確認事項1件の回答を要件へ反映する

## 実装結果

旧Q-088、旧Q-089を記録した。24時より前の休止を6人以下と同じく扱い選択肢を示すことで、7人より休止が有利になる問題をなくした。30分だけの応援や応援先の切り替えを目的関数⑩で抑える。⑨の負の値、T11の順位、Validatorとアプリケーションの責務、探索の時間切れ、休止の表示と延長保留、FIXの隊を減らす仮定、弓11の記法、旧い決定の注記を直した。作成者の仮定をA-11まで増やし、本文の参照が実在することをテストで確かめる

## 重要な判断

- 24時より前の休止は6人以下と同じく選択肢を示す（旧Q-088）
- 30分だけの応援をなるべくさせない（旧Q-089）

## 検証

- python tools/check.py 成功（116 passed）

## 未完了事項

- 対応後の再レビュー

## 正本への参照

- `docs/requirements/team-building/README.md`
- `docs/requirements/team-building/formation-rules.md`
- `docs/requirements/team-building/open-questions.md`
- `docs/requirements/team-building/output-and-screen.md`
- `docs/requirements/team-building/roster-input.md`
- `tests/test_repository_scope.py`
