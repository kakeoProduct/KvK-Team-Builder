---
type: session
id: 2026-10-18T130250Z-rereview-scope-and-termination
title: 再レビューの対象、投稿の重複防止、終わり方を定める
status: current
created_at: '2026-10-18T13:02:50Z'
base_commit: 87cd62bac15f1f6521af272e77081fe7c5ba3fd1
final_commit: 87cd62bac15f1f6521af272e77081fe7c5ba3fd1
tags:
- ai-harness
- review
related_paths:
- .agents/skills/create-github-pr/SKILL.md
- .agents/skills/implement/SKILL.md
- .agents/skills/review-kvk-change/SKILL.md
- .agents/skills/review-kvk-change/references/review-report-template.md
- .claude/skills/create-github-pr/SKILL.md
- .claude/skills/implement/SKILL.md
- .claude/skills/review-kvk-change/SKILL.md
- .claude/skills/review-kvk-change/references/review-report-template.md
- .github/pull_request_template.md
- AGENTS.md
- DEVELOPMENT.md
- docs/adr/0024-review-document-changes-and-requirements.md
- tests/test_ai_harness.py
---

# 再レビューの対象、投稿の重複防止、終わり方を定める

## 利用者の依頼

PR #44の再レビューの指摘へ対応する。見送れる誤字の修正を意味を変えないものに限り、再レビューはPR全体の差分を対象とする

## 実装結果

見送れる誤字の修正の範囲、再レビューの対象と重点、同じheadへの重複投稿の防止、Shouldだけが残る場合の終わり方、回答の反映先、テンプレートの「前回の指摘の判定」欄を定め、構造テストを加えた

## 重要な判断

- 誤字の修正から要件ID、数値、否定、識別子、規則の対象を変える修正を除く（利用者が承認）
- 再レビューはPR全体の差分を対象とし、前回のheadからのコミットを重点に見る（利用者が承認）
- 未コミットの変更へのレビュー結果は投稿しない

## 検証

- python tools/check.py 成功
- pytest tests/test_ai_harness.py tests/test_agent_hooks.py 47 passed

## 未完了事項

- 対応後の再レビュー

## 正本への参照

- `.agents/skills/create-github-pr/SKILL.md`
- `.agents/skills/implement/SKILL.md`
- `.agents/skills/review-kvk-change/SKILL.md`
- `.agents/skills/review-kvk-change/references/review-report-template.md`
- `.claude/skills/create-github-pr/SKILL.md`
- `.claude/skills/implement/SKILL.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.claude/skills/review-kvk-change/references/review-report-template.md`
- `.github/pull_request_template.md`
- `AGENTS.md`
- `DEVELOPMENT.md`
- `docs/adr/0024-review-document-changes-and-requirements.md`
- `tests/test_ai_harness.py`
