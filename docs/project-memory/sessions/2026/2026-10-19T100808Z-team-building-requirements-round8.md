---
type: session
id: 2026-10-19T100808Z-team-building-requirements-round8
title: 編成の要件定義書へ8回目の回答を反映し、人数の下限を一覧表にまとめる
status: current
created_at: '2026-10-19T10:08:08Z'
base_commit: 24efbc5de87050e8019f2b6cb8d56d0f396097fc
final_commit: 24efbc5de87050e8019f2b6cb8d56d0f396097fc
tags:
- requirements
- team-building
related_paths: []
---

# 編成の要件定義書へ8回目の回答を反映し、人数の下限を一覧表にまとめる

## 利用者の依頼

PR #43の5回目の再レビューのMust、Shouldと確認事項8件の回答を要件へ反映する

## 実装結果

旧Q-079〜旧Q-087として決定を記録した。序盤を戦闘開始からの1時間とし、人数が下限に満たない場合の扱いと選択肢をFRM-090の表へ集約した。上位隊の固定をなくさない決定によりFRM-028を廃止した。T11の記法と1種どうしの順、隊数を減らす細部、⑨の数え方、休止を①で数えることを決めた。決めきれない細部は作成者の仮定A-01〜A-06として記録し、未決事項はなくなった

## 重要な判断

- 序盤は戦闘開始からの1時間（旧Q-080）
- 細部は確認事項にせず作成者の仮定に記録する（利用者の依頼による改善）

## 検証

- python tools/check.py 成功（116 passed）

## 未完了事項

- 変更パス: docs/requirements/team-building/のREADME.md、formation-rules.md、open-questions.md、output-and-screen.md、roster-input.md（開始状態の保存が編集後になったため本文に記録）
- 対応後の再レビュー

## 正本への参照

- 利用者による明示的な記録依頼
