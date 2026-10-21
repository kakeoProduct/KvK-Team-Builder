---
type: session
id: 2026-10-19T124915Z-review-agents-refer-skill
title: Review Agentは確認事項の基準をSkillから参照し、自己点検リストを育てる
status: current
created_at: '2026-10-19T12:49:15Z'
base_commit: c2058ee122b0d47990ab14f4e6b9128997c721e2
final_commit: 707c4471327abb1b568295eca99f343389afc036
tags:
- ai-harness
- review
related_paths:
- .agents/skills/implement/SKILL.md
- .agents/skills/review-kvk-change/SKILL.md
- .agents/skills/review-kvk-change/references/review-report-template.md
- .agents/skills/review-kvk-change/references/self-check.md
- .claude/agents/kvk-architecture-reviewer.md
- .claude/agents/kvk-domain-reviewer.md
- .claude/agents/kvk-requirements-reviewer.md
- .claude/agents/kvk-test-reviewer.md
- .claude/skills/implement/SKILL.md
- .claude/skills/review-kvk-change/SKILL.md
- .claude/skills/review-kvk-change/references/review-report-template.md
- .claude/skills/review-kvk-change/references/self-check.md
- .codex/agents/kvk-architecture-reviewer.toml
- .codex/agents/kvk-domain-reviewer.toml
- .codex/agents/kvk-requirements-reviewer.toml
- .codex/agents/kvk-test-reviewer.toml
- AGENTS.md
- docs/adr/0024-review-document-changes-and-requirements.md
- tests/test_ai_harness.py
- tests/test_review_fingerprint.py
- tools/review_fingerprint.py
---

# Review Agentは確認事項の基準をSkillから参照し、自己点検リストを育てる

## 利用者の依頼

PR #44の7回目の再レビューの指摘と、自己点検リストの追加を承認なしに行う回答を反映する

## 実装結果

前回の振り返りの案を最初に反映し、自己点検リストをC12まで増やして出所を付けた。4つのReview Agentは確認事項の基準を写さずSkillを参照する。見送りの照合を主エージェントが行い、回数を再レビュー単位で数える。記録先を正本の順位に合わせ、implementの開始時に案を反映する。自己点検リストへの追加を承認不要とした

## 重要な判断

- 自己点検リストへの追加と見直しは項目ごとの承認を要らない（利用者が承認）
- Review Agentの定義に規則を写さず、Skillを正本として参照する（C2の手順の見直し）

## 検証

- python tools/check.py 成功
- 今回の規則4件を戻すとテストが失敗することを確認

## 未完了事項

- 対応後の再レビュー

## 正本への参照

- `.agents/skills/implement/SKILL.md`
- `.agents/skills/review-kvk-change/SKILL.md`
- `.agents/skills/review-kvk-change/references/review-report-template.md`
- `.agents/skills/review-kvk-change/references/self-check.md`
- `.claude/agents/kvk-architecture-reviewer.md`
- `.claude/agents/kvk-domain-reviewer.md`
- `.claude/agents/kvk-requirements-reviewer.md`
- `.claude/agents/kvk-test-reviewer.md`
- `.claude/skills/implement/SKILL.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.claude/skills/review-kvk-change/references/review-report-template.md`
- `.claude/skills/review-kvk-change/references/self-check.md`
- `.codex/agents/kvk-architecture-reviewer.toml`
- `.codex/agents/kvk-domain-reviewer.toml`
- `.codex/agents/kvk-requirements-reviewer.toml`
- `.codex/agents/kvk-test-reviewer.toml`
- `AGENTS.md`
- `docs/adr/0024-review-document-changes-and-requirements.md`
- `tests/test_ai_harness.py`
- `tests/test_review_fingerprint.py`
- `tools/review_fingerprint.py`
