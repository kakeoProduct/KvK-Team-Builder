---
type: session
id: 2026-08-11T075714Z-localize-codex-skills
title: Claude用SkillをCodex向けへ移行
status: current
created_at: '2026-08-11T07:57:14Z'
base_commit: 58a07923df65ef5a23441e5f76abac4ac2347d50
final_commit: 58a07923df65ef5a23441e5f76abac4ac2347d50
tags:
- ai-harness
- codex
- skill
related_paths:
- .agents/skills/ask-matt/PHASE-BOUNDARIES.md
- .agents/skills/ask-matt/SKILL.md
- .agents/skills/ask-matt/agents/openai.yaml
- .agents/skills/choose-skill/SKILL.md
- .agents/skills/choose-skill/agents/openai.yaml
- .agents/skills/claude-handoff/SKILL.md
- .agents/skills/claude-handoff/agents/openai.yaml
- .agents/skills/codex-handoff/SKILL.md
- .agents/skills/codex-handoff/agents/openai.yaml
- .agents/skills/git-guardrails-claude-code/SKILL.md
- .agents/skills/git-guardrails-claude-code/agents/openai.yaml
- .agents/skills/git-guardrails-claude-code/scripts/block-dangerous-git.sh
- .agents/skills/git-guardrails-codex/SKILL.md
- .agents/skills/git-guardrails-codex/agents/openai.yaml
- .agents/skills/git-guardrails-codex/scripts/block_dangerous_git.py
- skills-lock.json
- tests/test_ai_harness.py
---

# Claude用SkillをCodex向けへ移行

## 利用者の依頼

Claude固有のSkillをCodex向けに修正し、文言を日本語化する

## 実装結果

3個のClaude固有SkillをCodexネイティブなRepository固有Skillへ置換し、ロックとテストを整合させた

## 重要な判断

- 上流更新による上書きを避けるため、3個をskills-lock.jsonの管理対象から外してRepository固有Skillとして管理する
- Git保護HookはWindowsとLinuxで動くPython実装とし、CodexのPreToolUse deny JSONを返す

## 検証

- Skill構造検証: 3個すべて成功
- 前方テスト: choose-skillの選択とcodex-handoffのSubagent起動に成功
- python tools/check.py: Ruff、mypy、pytest 38件すべて成功

## 未完了事項

- 未完了なし

## 正本への参照

- `.agents/skills/ask-matt/PHASE-BOUNDARIES.md`
- `.agents/skills/ask-matt/SKILL.md`
- `.agents/skills/ask-matt/agents/openai.yaml`
- `.agents/skills/choose-skill/SKILL.md`
- `.agents/skills/choose-skill/agents/openai.yaml`
- `.agents/skills/claude-handoff/SKILL.md`
- `.agents/skills/claude-handoff/agents/openai.yaml`
- `.agents/skills/codex-handoff/SKILL.md`
- `.agents/skills/codex-handoff/agents/openai.yaml`
- `.agents/skills/git-guardrails-claude-code/SKILL.md`
- `.agents/skills/git-guardrails-claude-code/agents/openai.yaml`
- `.agents/skills/git-guardrails-claude-code/scripts/block-dangerous-git.sh`
- `.agents/skills/git-guardrails-codex/SKILL.md`
- `.agents/skills/git-guardrails-codex/agents/openai.yaml`
- `.agents/skills/git-guardrails-codex/scripts/block_dangerous_git.py`
- `skills-lock.json`
- `tests/test_ai_harness.py`
