---
type: session
id: 2026-10-18T024101Z-review-pr-comment
title: AIレビュー結果のテンプレート保存とPull Requestへの投稿
status: current
created_at: '2026-10-18T02:41:01Z'
base_commit: c37ac3f42a103d722f2a21ac6e5ab09a73cd3471
final_commit: c37ac3f42a103d722f2a21ac6e5ab09a73cd3471
tags:
- ai-harness
- review
related_paths:
- .agents/skills/create-github-pr/SKILL.md
- .agents/skills/review-kvk-change/SKILL.md
- .agents/skills/review-kvk-change/references/review-report-template.md
- .claude/skills/create-github-pr/SKILL.md
- .claude/skills/review-kvk-change/SKILL.md
- .claude/skills/review-kvk-change/references/review-report-template.md
- AGENTS.md
- DEVELOPMENT.md
- docs/adr/0022-post-ai-review-to-pull-request.md
- docs/adr/README.md
- tests/test_ai_harness.py
---

# AIレビュー結果のテンプレート保存とPull Requestへの投稿

## 利用者の依頼

AIレビュー（review-kvk-change）の結果をテンプレートで保持し、Pull Requestへ投稿するようにしたい

## 実装結果

review-kvk-changeにreferences/review-report-template.mdを追加し、tmp/reviews/への保存とgh pr commentでの投稿手順を追加。PRがない場合はcreate-github-prが作成後に投稿する。AGENTS.md、DEVELOPMENT.md、ADR 0022、構造テストを更新

## 重要な判断

- 投稿はコメントだけとし、Approve、Request changes、mergeは行わない。人間が承認を判断する（ADR 0007との整合）
- 対応後は対応状況を更新して新しいコメントとして投稿し、過去のコメントは編集しない

## 検証

- python tools/check.py: 成功

## 未完了事項

- 未完了なし

## 正本への参照

- `.agents/skills/create-github-pr/SKILL.md`
- `.agents/skills/review-kvk-change/SKILL.md`
- `.agents/skills/review-kvk-change/references/review-report-template.md`
- `.claude/skills/create-github-pr/SKILL.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.claude/skills/review-kvk-change/references/review-report-template.md`
- `AGENTS.md`
- `DEVELOPMENT.md`
- `docs/adr/0022-post-ai-review-to-pull-request.md`
- `docs/adr/README.md`
- `tests/test_ai_harness.py`
