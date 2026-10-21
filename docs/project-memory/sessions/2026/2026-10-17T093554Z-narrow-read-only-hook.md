---
type: session
id: 2026-10-17T093554Z-narrow-read-only-hook
title: 読み取り専用HookをPython起動の少ない形へ絞る
status: current
created_at: '2026-10-17T09:35:54Z'
base_commit: dc848bb99a0a52c06d283069704617b63604ed66
final_commit: dc848bb99a0a52c06d283069704617b63604ed66
tags:
- agent-hooks
- ai-harness
related_paths:
- .agents/skills/change-ai-harness/references/checklist.md
- .claude/settings.json
- .claude/skills/change-ai-harness/references/checklist.md
- CLAUDE.md
- DEVELOPMENT.md
- docs/adr/0018-enforce-read-only-agents-with-hook.md
- tests/test_agent_hooks.py
- tools/hooks/enforce_read_only_agent.py
---

# 読み取り専用HookをPython起動の少ない形へ絞る

## 利用者の依頼

ADR 0017を採用し、ADR 0018は別案を検討した上で案B（Hookの対象を書き込み得るToolに絞る）を採用する

## 実装結果

ADR 0017を採用にした。enforce_read_only_agent.pyのmatcherをBash、PowerShell、Monitor、編集Tool、Agent、MCPに絞り、内部Toolの許可リスト（HARNESS_TOOLS）を廃止した。ADR 0018、DEVELOPMENT.md、CLAUDE.md、checklistを更新した

## 重要な判断

- 全Tool対象は主Sessionの負荷と内部Tool追加時の報告不能が弱点で、未知Toolの拒否はAgentのtoolsで代替できるため絞った
- isolation: worktreeは既定branchから作られ未コミット差分が見えず、sandboxはSession全体にしか効かないため不採用

## 検証

- python -m pytest tests/test_agent_hooks.py: 15件成功
- python tools/check.py: 成功
- 新しいSessionのautoモードで、kvk-test-reviewerの`python -c "print(1)"`がHookに拒否され、結果の報告も届いた。ADR 0018を採用にした

## 未完了事項

- 未完了なし

## 正本への参照

- `.agents/skills/change-ai-harness/references/checklist.md`
- `.claude/settings.json`
- `.claude/skills/change-ai-harness/references/checklist.md`
- `CLAUDE.md`
- `DEVELOPMENT.md`
- `docs/adr/0018-enforce-read-only-agents-with-hook.md`
- `tests/test_agent_hooks.py`
- `tools/hooks/enforce_read_only_agent.py`
