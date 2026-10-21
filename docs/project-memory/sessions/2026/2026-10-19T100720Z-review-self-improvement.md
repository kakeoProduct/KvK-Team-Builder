---
type: session
id: 2026-10-19T100720Z-review-self-improvement
title: 指摘へ対応するたびに自己改善し、確認事項を絞る
status: current
created_at: '2026-10-19T10:07:20Z'
base_commit: 453f15046a4ee10ddd06d3c70320313b10e06820
final_commit: 453f15046a4ee10ddd06d3c70320313b10e06820
tags:
- ai-harness
- review
related_paths: []
---

# 指摘へ対応するたびに自己改善し、確認事項を絞る

## 利用者の依頼

PR #44の5回目の再レビューのMust、Shouldと回答を反映し、確認事項が減らない点の改善と、対応のたびに自己改善する仕組みを作る

## 実装結果

指紋で名前の変更を検出せず、未追跡のファイルを対象に含め、委譲の前後で比べるようにした。diffを常に記録し、重複の判定をtarget、head、diffの組にし、push後に$implementが投稿する。見送りの行に題名、場所、版、状態を持たせた。確認事項は必須条件、出力、操作が変わる点だけに絞り推奨案を添え、細部は作成者の仮定へ回す。自己点検リストと振り返りの手順を加え、繰り返した原因C8を足した

## 重要な判断

- push後の投稿は$implementが行う（利用者がAを選択）
- 無効になった見送りは無効と記して残す（利用者がAを選択）
- 自己点検リストへの追加は、同じPRで2回以上現れた原因について作成者が行う（利用者が依頼）

## 検証

- python tools/check.py 成功
- pytest tests/test_review_fingerprint.py tests/test_ai_harness.py tests/test_agent_hooks.py 58 passed

## 未完了事項

- 変更パス: review-kvk-change（SKILL.md、テンプレート、self-check.md）、create-github-pr、implement、4つのReview AgentのTOML、生成物、ADR 0024、AGENTS.md、DEVELOPMENT.md、tools/review_fingerprint.py、tests/（開始状態の保存が編集後になったため本文に記録。C8として自己点検リストに追加）
- 対応後の再レビュー

## 正本への参照

- 利用者による明示的な記録依頼
