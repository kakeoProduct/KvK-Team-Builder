---
type: session
id: 2026-10-18T130407Z-team-building-requirements-round4
title: 編成の要件定義書へ4回目の回答を反映する
status: current
created_at: '2026-10-18T13:04:07Z'
base_commit: 90e793f69c4ad1f0fb85da441ef1bf4bd6a102dc
final_commit: 90e793f69c4ad1f0fb85da441ef1bf4bd6a102dc
tags:
- requirements
- team-building
related_paths: []
---

# 編成の要件定義書へ4回目の回答を反映する

## 利用者の依頼

PR #43の再レビューで出した運用者への確認事項12件の回答を要件へ反映する

## 実装結果

旧Q-032〜旧Q-043として決定済みの事項へ記録し、リーダー不在、応援先、6人以下の扱い、延長時間、総力の合計、平均Gの同点、序盤の固定、通常モードのグループを要件へ反映した。目的関数の指標の数え方、出撃開始前の除外、分割案の結果型とテストの更新方針を加えた。待機を人数の上限に含めるかはQ-044として未決に残した

## 重要な判断

- 代理リーダーは当面アプリが決めない（旧Q-032）
- 応援先は第5隊以降とし、決める必要があれば出力前にダイアログで問い合わせる（旧Q-033）
- 序盤は20:00〜21:00で固定する（旧Q-042）

## 検証

- python tools/check.py 成功（116 passed）
- 構造テストが未記録の旧Qと分類表にない分類で失敗することを一時コピーで確認

## 未完了事項

- 変更パス: docs/requirements/team-building/のREADME.md、formation-rules.md、open-questions.md、output-and-screen.md、tests/test_repository_scope.py（開始状態の保存が編集後になったため本文に記録）
- Q-044の回答、対応後の再レビュー

## 正本への参照

- 利用者による明示的な記録依頼
