---
type: session
id: 2026-10-18T133525Z-team-building-requirements-round5
title: 編成の要件定義書へ5回目の回答を反映する
status: current
created_at: '2026-10-18T13:35:25Z'
base_commit: b5c2038659b3e73528b017674bfca81eb43a80e4
final_commit: b5c2038659b3e73528b017674bfca81eb43a80e4
tags:
- requirements
- team-building
related_paths: []
---

# 編成の要件定義書へ5回目の回答を反映する

## 利用者の依頼

PR #43の2回目の再レビューの確認事項13件の回答と指摘を要件へ反映する

## 実装結果

旧Q-044〜旧Q-055として決定を記録し、序盤の適用条件、◯最低の範囲、目的関数③を隊の平均Gで数えること、同点の扱い、応援先の条件、6人以下の明示的な許容（FRM-046）、隊ごとの上限8〜9人、名簿と同盟メンバー表の出力（OUT-013、OUT-014）、未定のリーダー、通常モードのグループを反映した。固定値の扱い、分割案の運用者の指定と結果型、FRM-038の検証方法、リーダー不在の警告（FRM-029）を加えた。歩T11の扱い（Q-056）と隊の中の並び順（Q-057）を未決に残した

## 重要な判断

- 6人以下は運用者が明示すれば警告つきで出力する（旧Q-050）
- 隊ごとの上限の上書きは8〜9人（旧Q-051）

## 検証

- python tools/check.py 成功（116 passed）
- 構造テストが旧のない決定済みの参照で失敗することを一時コピーで確認

## 未完了事項

- 変更パス: docs/requirements/team-building/のREADME.md、formation-rules.md、open-questions.md、output-and-screen.md、roster-input.md、tests/test_repository_scope.py（開始状態の保存が編集後になったため本文に記録）
- Q-056、Q-057の回答、対応後の再レビュー

## 正本への参照

- 利用者による明示的な記録依頼
