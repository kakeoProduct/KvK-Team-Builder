---
type: session
id: 2026-10-15T094201Z-agent-hooks-and-skill-cleanup
title: Agent HookとSkill構成の改善
status: current
created_at: '2026-10-15T09:42:01Z'
base_commit: 78ce31a2d22e53327d930e86cdaa30ffbf611c66
final_commit: 845da6591cf4f536b6894cb521b4d7970d10b13d
tags:
- agent-hooks
- ai-harness
related_paths:
- .agents/skills/change-kvk-rules/SKILL.md
- .agents/skills/git-guardrails-codex/SKILL.md
- .agents/skills/implement/SKILL.md
- .agents/skills/implement/agents/openai.yaml
- .agents/skills/maintain-project-memory/SKILL.md
- .agents/skills/maintain-project-memory/scripts/session_memory.py
- .agents/skills/migrate-to-shoehorn/SKILL.md
- .agents/skills/migrate-to-shoehorn/agents/openai.yaml
- .agents/skills/scaffold-exercises/SKILL.md
- .agents/skills/scaffold-exercises/agents/openai.yaml
- .agents/skills/setup-pre-commit/SKILL.md
- .agents/skills/setup-pre-commit/agents/openai.yaml
- .agents/skills/setup-ts-deep-modules/SKILL.md
- .agents/skills/setup-ts-deep-modules/agents/openai.yaml
- .agents/skills/setup-ts-deep-modules/dependency-cruiser.config.cjs
- .claude/settings.json
- .claude/skills/change-kvk-rules/SKILL.md
- .claude/skills/implement/SKILL.md
- .claude/skills/maintain-project-memory/SKILL.md
- .claude/skills/maintain-project-memory/scripts/session_memory.py
- .claude/skills/migrate-to-shoehorn/SKILL.md
- .claude/skills/scaffold-exercises/SKILL.md
- .claude/skills/setup-pre-commit/SKILL.md
- .claude/skills/setup-ts-deep-modules/SKILL.md
- .claude/skills/setup-ts-deep-modules/dependency-cruiser.config.cjs
- AGENTS.md
- CLAUDE.md
- DEVELOPMENT.md
- docs/adr/0014-enforce-agent-workflow-with-hooks.md
- docs/adr/README.md
- skills-lock.json
- tests/test_agent_hooks.py
- tests/test_ai_harness.py
- tests/test_preview_output.py
- tools/hooks/block_dangerous_git.py
- tools/hooks/project_memory_hook.py
- tools/preview_output.py
---

# Agent HookとSkill構成の改善

## 利用者の依頼

beamnxwのOpus 5.5以降の投稿調査に基づくSkill改善6項目をすべて実施する

## 実装結果

Claude CodeのGit保護・共有記憶Hook、生成結果確認Script、implementのRepository固有化、TS向けSkill削除、昇格ヒントを追加しADR 0014へ記録した

## 重要な判断

- Git保護Scriptをtools/hooksへ移しCodexとClaude Codeで共有し、Claude Codeでは通常pushだけ利用者確認にする
- Stop Hookは未記録の変更を1 Sessionに1回だけ催促し、finishの自動実行はしない
- 生成結果の差分はCP-SATの探索に左右されるため合否に使わない
- HookのJSON入出力はWindowsのcp932を避けUTF-8で扱う

## 検証

- python tools/check.py: 成功（57 passed）
- システムPythonでGit保護Hookと共有記憶Stop Hookを手動実行: 想定どおり

## 未完了事項

- Claude Codeの実Session上でのHook動作は次回Session開始時に確認する
- ADR 0014は提案中

## 正本への参照

- `.agents/skills/change-kvk-rules/SKILL.md`
- `.agents/skills/git-guardrails-codex/SKILL.md`
- `.agents/skills/implement/SKILL.md`
- `.agents/skills/implement/agents/openai.yaml`
- `.agents/skills/maintain-project-memory/SKILL.md`
- `.agents/skills/maintain-project-memory/scripts/session_memory.py`
- `.agents/skills/migrate-to-shoehorn/SKILL.md`
- `.agents/skills/migrate-to-shoehorn/agents/openai.yaml`
- `.agents/skills/scaffold-exercises/SKILL.md`
- `.agents/skills/scaffold-exercises/agents/openai.yaml`
- `.agents/skills/setup-pre-commit/SKILL.md`
- `.agents/skills/setup-pre-commit/agents/openai.yaml`
- `.agents/skills/setup-ts-deep-modules/SKILL.md`
- `.agents/skills/setup-ts-deep-modules/agents/openai.yaml`
- `.agents/skills/setup-ts-deep-modules/dependency-cruiser.config.cjs`
- `.claude/settings.json`
- `.claude/skills/change-kvk-rules/SKILL.md`
- `.claude/skills/implement/SKILL.md`
- `.claude/skills/maintain-project-memory/SKILL.md`
- `.claude/skills/maintain-project-memory/scripts/session_memory.py`
- `.claude/skills/migrate-to-shoehorn/SKILL.md`
- `.claude/skills/scaffold-exercises/SKILL.md`
- `.claude/skills/setup-pre-commit/SKILL.md`
- `.claude/skills/setup-ts-deep-modules/SKILL.md`
- `.claude/skills/setup-ts-deep-modules/dependency-cruiser.config.cjs`
- `AGENTS.md`
- `CLAUDE.md`
- `DEVELOPMENT.md`
- `docs/adr/0014-enforce-agent-workflow-with-hooks.md`
- `docs/adr/README.md`
- `skills-lock.json`
- `tests/test_agent_hooks.py`
- `tests/test_ai_harness.py`
- `tests/test_preview_output.py`
- `tools/hooks/block_dangerous_git.py`
- `tools/hooks/project_memory_hook.py`
- `tools/preview_output.py`
