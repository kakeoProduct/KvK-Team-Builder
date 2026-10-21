---
type: session
id: 2026-10-18T140613Z-review-skip-and-acceptance-section
title: 見送れる変更を3つにそろえ、Shouldの見送りの節とPR本文への追記を定める
status: current
created_at: '2026-10-18T14:06:13Z'
base_commit: 300931d7221246492494ee15a2fe367e054ef872
final_commit: 300931d7221246492494ee15a2fe367e054ef872
tags:
- ai-harness
- review
related_paths: []
---

# 見送れる変更を3つにそろえ、Shouldの見送りの節とPR本文への追記を定める

## 利用者の依頼

PR #44の3回目の再レビューのMust、Shouldと、確認事項への回答を反映する

## 実装結果

見送れる変更（誤字だけ、共有記憶だけ、誤字とその共有記憶だけ）をすべての手順にそろえた。名前の扱いを基準ブランチにコミット済みのものに限り、新しく加わるデータの検査を残した。レビュー結果に見送りの節を設け、PR本文への追記をSkillの読み取り専用の例外に加えた。終わる条件に前回のMustの解消と確認事項の回答を加え、Ready前にレビューしたheadを確かめるようにした

## 重要な判断

- 書いてよい名前は基準ブランチにコミット済みのものだけ（利用者が承認）
- Shouldの見送りはレビュー結果の見送りの節に記録し、PR本文への追記はレビューのSkillが行う（利用者が承認）
- 運用者への確認事項が未回答なら繰り返しを終えない（利用者が承認）

## 検証

- python tools/check.py 成功
- 規則を3件戻すと構造テストが失敗することを確認

## 未完了事項

- 変更パス: review-kvk-change、create-github-pr、implementのSKILL.mdと生成物、テンプレート、ADR 0024、AGENTS.md、DEVELOPMENT.md、PRテンプレート、kvk-requirements-reviewer.tomlと生成物、tests/test_ai_harness.py（開始状態の保存が編集後になったため本文に記録）
- 対応後の再レビュー

## 正本への参照

- 利用者による明示的な記録依頼
