---
type: session
id: 2026-10-15T104835Z-parallel-session-worktree-harness
title: 並行Sessionのworktree分離と検証可能な完了・調査・レビュー
status: current
created_at: '2026-10-15T10:48:35Z'
base_commit: dc848bb99a0a52c06d283069704617b63604ed66
final_commit: dc848bb99a0a52c06d283069704617b63604ed66
tags:
- agent-hooks
- ai-harness
related_paths:
- .agents/skills/choose-skill/SKILL.md
- .agents/skills/git-guardrails-codex/SKILL.md
- .agents/skills/implement/SKILL.md
- .agents/skills/maintain-project-memory/SKILL.md
- .agents/skills/maintain-project-memory/scripts/session_memory.py
- .agents/skills/research/SKILL.md
- .agents/skills/research/agents/openai.yaml
- .agents/skills/review-kvk-change/SKILL.md
- .claude/agents/kvk-architecture-reviewer.md
- .claude/agents/kvk-domain-reviewer.md
- .claude/agents/kvk-test-reviewer.md
- .claude/settings.json
- .claude/skills/choose-skill/SKILL.md
- .claude/skills/implement/SKILL.md
- .claude/skills/maintain-project-memory/SKILL.md
- .claude/skills/maintain-project-memory/scripts/session_memory.py
- .claude/skills/research/SKILL.md
- .claude/skills/review-kvk-change/SKILL.md
- .codex/agents/kvk-architecture-reviewer.toml
- .codex/agents/kvk-domain-reviewer.toml
- .codex/agents/kvk-test-reviewer.toml
- .gitignore
- AGENTS.md
- CLAUDE.md
- DEVELOPMENT.md
- docs/adr/0015-isolate-parallel-sessions-and-verify-claims.md
- docs/adr/README.md
- skills-lock.json
- tests/test_agent_hooks.py
- tests/test_ai_harness.py
- tools/hooks/block_dangerous_git.py
- tools/hooks/project_memory_hook.py
---

# 並行Sessionのworktree分離と検証可能な完了・調査・レビュー

## 利用者の依頼

Opus 5.5向けHarness事例の調査結果から、適用できる改善をSkill群へすべて適用する。worktreeは別Sessionが使用中のときだけ使う

## 実装結果

permissions.deny、別Session検出とdiscard、Hookのworktree追従、worktree remove --force拒否、implementのworktree手順と/goal、researchの日本語固有Skill化、レビューの未確定の懸念を追加した。HookがLinuxでWindows用venvを起動する既存不具合も修正した

## 重要な判断

- 使用中の判定は開始状態のlast_seen_atで行い、3時間で失効させる（ADR 0015）
- 移動時は元の開始状態をfinishでなくdiscardで破棄し、別Sessionの差分を記録しない
- .claude/rules/によるAGENTS.md分割はCodexとの正本二重化になるため見送った

## 検証

- python tools/check.py: 成功（75 passed）
- 実Repositoryでsession-start Hookを実行: 別Session使用中のworktree案内を確認

## 未完了事項

- この環境はGitのdubious ownershipでHookのGit操作が失敗する。safe.directoryの設定は利用者判断
- 変更は未コミット。ADR 0015は提案中

## 正本への参照

- `.agents/skills/choose-skill/SKILL.md`
- `.agents/skills/git-guardrails-codex/SKILL.md`
- `.agents/skills/implement/SKILL.md`
- `.agents/skills/maintain-project-memory/SKILL.md`
- `.agents/skills/maintain-project-memory/scripts/session_memory.py`
- `.agents/skills/research/SKILL.md`
- `.agents/skills/research/agents/openai.yaml`
- `.agents/skills/review-kvk-change/SKILL.md`
- `.claude/agents/kvk-architecture-reviewer.md`
- `.claude/agents/kvk-domain-reviewer.md`
- `.claude/agents/kvk-test-reviewer.md`
- `.claude/settings.json`
- `.claude/skills/choose-skill/SKILL.md`
- `.claude/skills/implement/SKILL.md`
- `.claude/skills/maintain-project-memory/SKILL.md`
- `.claude/skills/maintain-project-memory/scripts/session_memory.py`
- `.claude/skills/research/SKILL.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.codex/agents/kvk-architecture-reviewer.toml`
- `.codex/agents/kvk-domain-reviewer.toml`
- `.codex/agents/kvk-test-reviewer.toml`
- `.gitignore`
- `AGENTS.md`
- `CLAUDE.md`
- `DEVELOPMENT.md`
- `docs/adr/0015-isolate-parallel-sessions-and-verify-claims.md`
- `docs/adr/README.md`
- `skills-lock.json`
- `tests/test_agent_hooks.py`
- `tests/test_ai_harness.py`
- `tools/hooks/block_dangerous_git.py`
- `tools/hooks/project_memory_hook.py`
