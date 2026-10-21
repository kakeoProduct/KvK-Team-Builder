---
type: session
id: 2026-10-19T093915Z-team-building-requirements-round7
title: 編成の要件定義書へ7回目の回答を反映する
status: current
created_at: '2026-10-19T09:39:15Z'
base_commit: 7fa49b115bd70858a3502e71c4e19869428d7954
final_commit: 7fa49b115bd70858a3502e71c4e19869428d7954
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

# 編成の要件定義書へ7回目の回答を反映する

## 利用者の依頼

PR #43の4回目の再レビューのShouldと確認事項12件の回答を要件へ反映する

## 実装結果

旧Q-057、旧Q-068〜旧Q-078として決定を記録した。隊数を減らす操作（FRM-005）、出撃の休止と再開（FRM-048）、最適性を示せない場合の警告（FRM-049）を加えた。T11は弓兵だけでも数え、ROS-042の歩兵基準を置き換えた。目的関数に24時以降の★（⑧）とセットの応援先（⑨）を加え、並び順、表示の形、遅れて出撃の条件、FRM-047の検査の範囲、CLIの回答の書き方、FRM-038の検証方法を決めた。なくした隊のリーダーの扱いをQ-079として未決に残した

## 重要な判断

- 隊数を減らす選択肢は、番号の大きな隊をなくして編成をやり直す（旧Q-068）
- 隊の中の同じ区分の並び順は、運用者が任せたためGの高い順、同じGは参加者一覧の順とした（旧Q-057）

## 検証

- python tools/check.py 成功（116 passed）
- 構造テストに決定済みの番号の重複の検査を加え、旧のない参照の残りを検出して直した

## 未完了事項

- Q-079の回答、対応後の再レビュー

## 正本への参照

- `docs/requirements/team-building/README.md`
- `docs/requirements/team-building/formation-rules.md`
- `docs/requirements/team-building/open-questions.md`
- `docs/requirements/team-building/output-and-screen.md`
- `docs/requirements/team-building/roster-input.md`
- `tests/test_repository_scope.py`
