---
type: session
id: 2026-10-19T093845Z-review-fingerprint-and-verdict
title: コミット前のレビューを指紋で照合し、未回答の確認事項を承認不可とする
status: current
created_at: '2026-10-19T09:38:45Z'
base_commit: f3ff7856517e82c69282f9b93d647bc11e5406fa
final_commit: f3ff7856517e82c69282f9b93d647bc11e5406fa
tags:
- ai-harness
- review
related_paths:
- .agents/skills/create-github-pr/SKILL.md
- .agents/skills/implement/SKILL.md
- .agents/skills/review-kvk-change/SKILL.md
- .agents/skills/review-kvk-change/references/review-report-template.md
- .claude/agents/kvk-requirements-reviewer.md
- .claude/skills/create-github-pr/SKILL.md
- .claude/skills/implement/SKILL.md
- .claude/skills/review-kvk-change/SKILL.md
- .claude/skills/review-kvk-change/references/review-report-template.md
- .codex/agents/kvk-requirements-reviewer.toml
- DEVELOPMENT.md
- docs/adr/0024-review-document-changes-and-requirements.md
- tests/test_ai_harness.py
- tests/test_review_fingerprint.py
- tools/review_fingerprint.py
---

# コミット前のレビューを指紋で照合し、未回答の確認事項を承認不可とする

## 利用者の依頼

PR #44の4回目の再レビューのMust、Shouldと、確認事項への回答を反映する

## 実装結果

tools/review_fingerprint.pyでレビューした未コミットの変更の指紋を計算し、印のdiffと照合して投稿とReadyを判断するようにした。確認事項が未回答か前回のMustが解消していない場合の承認判定を承認不可とした。見送りの節を再レビューで引き継ぎ、対象が変われば再判断する。PR本文の書き戻しをUTF-8と再取得で保全し、フォールバックで要件担当の定義を読むようにした

## 重要な判断

- コミット前のレビューは指紋が一致すれば投稿する（利用者がAを選択）
- 未回答の確認事項と未解消のMustは承認不可（利用者が承認）
- 別PRへ引き継いだ確認事項と保留の回答は回答済み（利用者が承認）

## 検証

- python tools/check.py 成功
- pytest tests/test_review_fingerprint.py tests/test_ai_harness.py tests/test_agent_hooks.py 51 passed

## 未完了事項

- 対応後の再レビュー

## 正本への参照

- `.agents/skills/create-github-pr/SKILL.md`
- `.agents/skills/implement/SKILL.md`
- `.agents/skills/review-kvk-change/SKILL.md`
- `.agents/skills/review-kvk-change/references/review-report-template.md`
- `.claude/agents/kvk-requirements-reviewer.md`
- `.claude/skills/create-github-pr/SKILL.md`
- `.claude/skills/implement/SKILL.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.claude/skills/review-kvk-change/references/review-report-template.md`
- `.codex/agents/kvk-requirements-reviewer.toml`
- `DEVELOPMENT.md`
- `docs/adr/0024-review-document-changes-and-requirements.md`
- `tests/test_ai_harness.py`
- `tests/test_review_fingerprint.py`
- `tools/review_fingerprint.py`
