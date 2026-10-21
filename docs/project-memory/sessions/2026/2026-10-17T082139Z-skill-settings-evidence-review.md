---
type: session
id: 2026-10-17T082139Z-skill-settings-evidence-review
title: Claude Code専用Skill設定と調査結果の独立検証
status: current
created_at: '2026-10-17T08:21:39Z'
base_commit: dc848bb99a0a52c06d283069704617b63604ed66
final_commit: dc848bb99a0a52c06d283069704617b63604ed66
tags:
- ai-harness
related_paths:
- .agents/skills/change-ai-harness/references/checklist.md
- .agents/skills/choose-skill/SKILL.md
- .agents/skills/research/SKILL.md
- .agents/skills/research/agents/openai.yaml
- .claude/agents/evidence-reviewer.md
- .claude/skills/change-ai-harness/references/checklist.md
- .claude/skills/choose-skill/SKILL.md
- .claude/skills/research/SKILL.md
- .claude/skills/review-kvk-change/SKILL.md
- .codex/agents/evidence-reviewer.toml
- AGENTS.md
- CLAUDE.md
- DEVELOPMENT.md
- docs/adr/0017-enforce-skill-settings-and-review-research-evidence.md
- docs/adr/README.md
- tests/test_ai_harness.py
- tools/sync_agent_config.py
---

# Claude Code専用Skill設定と調査結果の独立検証

## 利用者の依頼

beamnxwのOpus 5.5以降の投稿を基にした改善候補のうち、中優先度以上（Skill設定の注入、researchの条件付き保存、証拠Reviewer）を採用する

## 実装結果

同期ScriptにCLAUDE_SKILL_SETTINGSとCLAUDE_AGENT_TOOLSを追加し、review-kvk-changeへdisallowed-toolsとeffort、researchへcontext: forkを生成物だけに付与した。読み取り専用のevidence-reviewerを追加し、researchを下書き（tmp/research/）の独立検証と依頼時だけの保存へ変更した

## 重要な判断

- Codexとの互換性を確認できないため、Claude Code専用の項目は正本でなく同期Scriptから生成物へ加える（ADR 0017）
- disallowed-toolsは次の利用者Messageで解除されるため、レビュー後の修正依頼を妨げない
- evidence-reviewerはコードレビュー用でないためMust/Should/Niceを適用しない

## 検証

- python -m pytest tests/test_ai_harness.py: 変更前に4件失敗、変更後27件成功
- python tools/check.py: 78件成功

## 未完了事項

- Codexの読み取り専用sandboxでevidence-reviewerがWeb取得できるかは未確認
- low優先度の候補（implementの停止条件の数値化、apple-designの視覚確認）は未採用

## 正本への参照

- `.agents/skills/change-ai-harness/references/checklist.md`
- `.agents/skills/choose-skill/SKILL.md`
- `.agents/skills/research/SKILL.md`
- `.agents/skills/research/agents/openai.yaml`
- `.claude/agents/evidence-reviewer.md`
- `.claude/skills/change-ai-harness/references/checklist.md`
- `.claude/skills/choose-skill/SKILL.md`
- `.claude/skills/research/SKILL.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.codex/agents/evidence-reviewer.toml`
- `AGENTS.md`
- `CLAUDE.md`
- `DEVELOPMENT.md`
- `docs/adr/0017-enforce-skill-settings-and-review-research-evidence.md`
- `docs/adr/README.md`
- `tests/test_ai_harness.py`
- `tools/sync_agent_config.py`
