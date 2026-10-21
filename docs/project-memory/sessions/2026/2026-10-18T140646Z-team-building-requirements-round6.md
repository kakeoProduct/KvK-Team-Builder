---
type: session
id: 2026-10-18T140646Z-team-building-requirements-round6
title: 編成の要件定義書へ6回目の回答を反映する
status: current
created_at: '2026-10-18T14:06:46Z'
base_commit: 390a7adeab28b3b132eb32bc6ad1130a89fcada6
final_commit: 390a7adeab28b3b132eb32bc6ad1130a89fcada6
tags:
- requirements
- team-building
related_paths: []
---

# 編成の要件定義書へ6回目の回答を反映する

## 利用者の依頼

PR #43の3回目の再レビューのMust、Shouldと確認事項11件の回答を要件へ反映する

## 実装結果

旧Q-056〜旧Q-067として決定を記録した。序盤は戦闘開始20:00の回だけ（戦闘開始は20:00か21:00）、序盤の8人未満も明示すれば許す、T11の比率は兵種の数で数える、応援先は時間帯ごと、別枠の上位隊リーダーは7人と警告と見出しの「リーダー不在」、注記の上限、同盟メンバー表の出力、警告の重なり、0人の隊を反映した。運用者の指定の検証（FRM-047）、結果型の3分類、CLIでの回答の渡し方、FRM-038の検証、固定値の一覧を加えた。並び順の残り（Q-057）と「隊数を減らす」の意味（Q-068）を未決に残した

## 重要な判断

- 序盤の規則は戦闘開始20:00の回だけに適用する（旧Q-058）
- T11の比率は歩兵、騎兵、弓兵のT11の兵種の数で数える（旧Q-056、作成者の解釈を含む）

## 検証

- python tools/check.py 成功（116 passed）
- 構造テストにQの番号の連続性の検査を追加

## 未完了事項

- 変更パス: docs/requirements/team-building/のREADME.md、formation-rules.md、open-questions.md、output-and-screen.md、roster-input.md、docs/adr/0023、tests/test_repository_scope.py（開始状態の保存が編集後になったため本文に記録）
- Q-057、Q-068の回答、対応後の再レビュー

## 正本への参照

- 利用者による明示的な記録依頼
