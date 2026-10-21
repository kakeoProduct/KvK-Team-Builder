---
type: session
id: 2026-07-20T134853Z-review-decision-levels
title: レビュー指摘を人間向け3段階へ変更
status: current
created_at: '2026-07-20T13:48:53Z'
base_commit: 0f2c5eb9aeda8b0ea51ad89b051477923c096ca9
final_commit: 0f2c5eb9aeda8b0ea51ad89b051477923c096ca9
tags:
- ai-harness
- review
- skill
related_paths:
- .agents/skills/review-kvk-change/SKILL.md
- .codex/agents/kvk-architecture-reviewer.toml
- .codex/agents/kvk-domain-reviewer.toml
- .codex/agents/kvk-test-reviewer.toml
- AGENTS.md
- docs/adr/0007-human-review-decision-levels.md
- docs/adr/README.md
- tests/test_ai_harness.py
---

# レビュー指摘を人間向け3段階へ変更

## 利用者の依頼

レビューSkillをMust・Should・Niceの3段階で報告できるようにする

## 実装結果

レビューSkill、3つの専門Reviewer、Repository規約を承認判断に基づく3段階へ統一し、承認判定と回帰Testを追加した

## 重要な判断

- Mustは承認不可、Shouldは人間による修正またはリスク受容の要判断、Niceは承認を妨げない任意改善とした
- ADR 0002の重大度分類だけをADR 0007で置き換え、読み取り専用と根拠提示の方針は維持した

## 検証

- quick_validate.py .agents/skills/review-kvk-change: 成功
- python tools/check.py: Ruff、mypy、pytest 31件すべて成功

## 未完了事項

- なし

## 正本への参照

- `.agents/skills/review-kvk-change/SKILL.md`
- `.codex/agents/kvk-architecture-reviewer.toml`
- `.codex/agents/kvk-domain-reviewer.toml`
- `.codex/agents/kvk-test-reviewer.toml`
- `AGENTS.md`
- `docs/adr/0007-human-review-decision-levels.md`
- `docs/adr/README.md`
- `tests/test_ai_harness.py`
