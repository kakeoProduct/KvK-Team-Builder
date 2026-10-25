---
type: session
id: 2026-10-25T091822Z-subagent-operations
title: Review Agentのモデルとターン上限を固定し、Codexでも読み取り専用と結果の形式を強制する
status: current
created_at: '2026-10-25T09:18:22Z'
base_commit: 456055f29e8f8c9e7c1a911158b2599b4d44f7bc
final_commit: 456055f29e8f8c9e7c1a911158b2599b4d44f7bc
tags:
- ai-harness
related_paths:
- .agents/skills/change-ai-harness/references/checklist.md
- .agents/skills/create-github-pr/SKILL.md
- .agents/skills/git-guardrails-codex/SKILL.md
- .agents/skills/implement/SKILL.md
- .agents/skills/research/SKILL.md
- .agents/skills/review-kvk-change/SKILL.md
- .agents/skills/review-kvk-change/references/self-check.md
- .claude/agents/evidence-reviewer.md
- .claude/agents/kvk-architecture-reviewer.md
- .claude/agents/kvk-domain-reviewer.md
- .claude/agents/kvk-requirements-reviewer.md
- .claude/agents/kvk-test-reviewer.md
- .claude/settings.json
- .claude/skills/change-ai-harness/references/checklist.md
- .claude/skills/create-github-pr/SKILL.md
- .claude/skills/implement/SKILL.md
- .claude/skills/research/SKILL.md
- .claude/skills/review-kvk-change/SKILL.md
- .claude/skills/review-kvk-change/references/self-check.md
- .codex/agents/evidence-reviewer.toml
- .codex/agents/kvk-architecture-reviewer.toml
- .codex/agents/kvk-domain-reviewer.toml
- .codex/agents/kvk-requirements-reviewer.toml
- .codex/agents/kvk-test-reviewer.toml
- .codex/hooks.json
- AGENTS.md
- CLAUDE.md
- DEVELOPMENT.md
- docs/adr/0031-subagent-models-limits-and-codex-read-only.md
- docs/adr/README.md
- tests/test_agent_hooks.py
- tests/test_ai_harness.py
- tools/hooks/check_review_report.py
- tools/hooks/enforce_read_only_agent.py
- tools/sync_agent_config.py
---

# Review Agentのモデルとターン上限を固定し、Codexでも読み取り専用と結果の形式を強制する

## 利用者の依頼

公式情報でサブエージェント運用を見直し、Codexの親SessionをAutoのまま読み取り専用を強制する、modelの明示、SubagentStopでの結果の形式の検査、maxTurnsの設定を行う。途中でGit保護Hookの.codex/hooks.jsonへの登録と、devの取り込みも依頼された

## 実装結果

.codex/hooks.jsonを追跡し、Git保護、enforce_read_only_agent.py、check_review_report.pyを登録した。Review Agentのmodel（Claude Code: 要件・アーキテクチャ・証拠はopus、ほかはsonnet、Codex: gpt-6.1-solとgpt-6-luna）とmaxTurns（40、アーキテクチャと証拠は60）を固定した。読み取り専用の判定をPOSIXとして行い、$、\、{}、全角の引用符を全OSで、単一引用符、^、%、!をWindowsで丸ごと拒否し、pytest、sort、findを許可リストにした。ADR 0031と規約、Skill、自己点検リスト（C17追加、C7見直し）を更新した

## 重要な判断

- Codexはcustom agentのsandbox_modeを適用しないため、読み取り専用はClaude CodeとCodexのPreToolUse Hookで強制する（ADR 0031）
- Shellごとに解釈が違う記号は、記号ごとに並べず丸ごと拒否する。利用者が承認した
- （作成者の仮定）主Sessionは、レビュー担当と$researchを起動する前に読み取り専用の強制を確かめ、$researchへは結果を渡す。確かめられなければ逐次の確認か独立検証なしにする。利用者が/researchを直接起動した場合は独立検証をしない
- （作成者の仮定）maxTurnsで止まった担当には続きを指示し、見出しが欠けた結果は不完全として主Sessionが確認し直す
- （作成者の仮定）CodexではGit保護Hookがpushを拒否するため、$create-github-prと$implementはpushを利用者に頼み、push済みを確かめて続ける
- dev側でADR 0029とADR 0030が使われたため、このADRを0031へ振り直した

## 検証

- python tools/check.py: 212件成功
- $review-kvk-change: 初回と再レビュー6回。最終は4担当ともMustとShouldなしの承認候補

## 未完了事項

- Codexの実機とWindowsでのHookの動作、新しいClaude Code SessionでのSubagentStop Hookの動作は未確認
- コミット、push、Pull Requestの作成は未実施。レビュー結果のNice（N47〜N51）は任意

## 正本への参照

- `.agents/skills/change-ai-harness/references/checklist.md`
- `.agents/skills/create-github-pr/SKILL.md`
- `.agents/skills/git-guardrails-codex/SKILL.md`
- `.agents/skills/implement/SKILL.md`
- `.agents/skills/research/SKILL.md`
- `.agents/skills/review-kvk-change/SKILL.md`
- `.agents/skills/review-kvk-change/references/self-check.md`
- `.claude/agents/evidence-reviewer.md`
- `.claude/agents/kvk-architecture-reviewer.md`
- `.claude/agents/kvk-domain-reviewer.md`
- `.claude/agents/kvk-requirements-reviewer.md`
- `.claude/agents/kvk-test-reviewer.md`
- `.claude/settings.json`
- `.claude/skills/change-ai-harness/references/checklist.md`
- `.claude/skills/create-github-pr/SKILL.md`
- `.claude/skills/implement/SKILL.md`
- `.claude/skills/research/SKILL.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.claude/skills/review-kvk-change/references/self-check.md`
- `.codex/agents/evidence-reviewer.toml`
- `.codex/agents/kvk-architecture-reviewer.toml`
- `.codex/agents/kvk-domain-reviewer.toml`
- `.codex/agents/kvk-requirements-reviewer.toml`
- `.codex/agents/kvk-test-reviewer.toml`
- `.codex/hooks.json`
- `AGENTS.md`
- `CLAUDE.md`
- `DEVELOPMENT.md`
- `docs/adr/0031-subagent-models-limits-and-codex-read-only.md`
- `docs/adr/README.md`
- `tests/test_agent_hooks.py`
- `tests/test_ai_harness.py`
- `tools/hooks/check_review_report.py`
- `tools/hooks/enforce_read_only_agent.py`
- `tools/sync_agent_config.py`
