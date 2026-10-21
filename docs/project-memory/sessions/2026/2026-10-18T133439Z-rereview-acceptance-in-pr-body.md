---
type: session
id: 2026-10-18T133439Z-rereview-acceptance-in-pr-body
title: Shouldの受容をPR本文へ記録し、Mustは見送れないと定める
status: current
created_at: '2026-10-18T13:34:39Z'
base_commit: 7f653459f753c9b68306a844a7c6358bb5af404a
final_commit: 7f653459f753c9b68306a844a7c6358bb5af404a
tags:
- ai-harness
- review
related_paths: []
---

# Shouldの受容をPR本文へ記録し、Mustは見送れないと定める

## 利用者の依頼

PR #44の2回目の再レビューの指摘と確認事項への回答を反映する

## 実装結果

Shouldの見送りはPR本文の「判断と影響」へ記録し、Mustは見送れないと定めた。投稿前のheadの一致と投稿者の確認、失敗時に投稿もpushもしないこと、PR作成時の投稿の確認、誤字とその共有記憶だけの変更の見送り、tests/とsample/の試験データの扱いを加え、構造テストを広げた

## 重要な判断

- Shouldの見送りの記録先はPR本文（利用者が承認）
- Mustはリスクを受け入れても見送れない（利用者が承認）
- Repositoryにコミット済みのtests/とsample/の試験データの名前はレビュー結果に書いてよい（利用者が承認）

## 検証

- python tools/check.py 成功
- pytest tests/test_ai_harness.py tests/test_agent_hooks.py 47 passed

## 未完了事項

- 変更パス: review-kvk-change、create-github-pr、implementのSKILL.mdと生成物、テンプレート、ADR 0022、ADR 0024、AGENTS.md、kvk-requirements-reviewer.tomlと生成物、tests/test_ai_harness.py（開始状態の保存が編集後になったため本文に記録）
- 対応後の再レビュー

## 正本への参照

- 利用者による明示的な記録依頼
