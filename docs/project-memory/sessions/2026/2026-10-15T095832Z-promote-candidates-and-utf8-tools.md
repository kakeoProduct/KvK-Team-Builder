---
type: session
id: 2026-10-15T095832Z-promote-candidates-and-utf8-tools
title: ADR 0014の採用と昇格候補の作成
status: current
created_at: '2026-10-15T09:58:32Z'
base_commit: ec979f05d4a6ab5f2346255033d8b7f1549acd41
final_commit: 44333d22faba8376b118571481e2024b092240dc
tags:
- ai-harness
- windows
related_paths:
- docs/adr/0014-enforce-agent-workflow-with-hooks.md
- tests/test_agent_hooks.py
- tests/test_tool_output_encoding.py
- tools/hooks/block_dangerous_git.py
- tools/hooks/project_memory_hook.py
- tools/preview_output.py
---

# ADR 0014の採用と昇格候補の作成

## 利用者の依頼

ADR 0014を採用し、ai-harnessの昇格候補を作成してPRを作る

## 実装結果

ADR 0014を採用へ更新し、昇格候補2件を作成した。マージ済みCI修正の方針に合わせ、新規Tool 3件の出力をUTF-8へ固定した

## 重要な判断

- ai-harnessの反復はAIハーネス変更時の整合手順としてSkill化を提案する
- Windowsの文字コード問題は3回目の発生のためAGENTS.md規約への昇格候補にした

## 検証

- python tools/check.py: 成功（62 passed）
- session_memory.py validate: 成功（候補2件）

## 未完了事項

- 昇格候補2件の昇格は利用者の承認待ち

## 正本への参照

- `docs/adr/0014-enforce-agent-workflow-with-hooks.md`
- `tests/test_agent_hooks.py`
- `tests/test_tool_output_encoding.py`
- `tools/hooks/block_dangerous_git.py`
- `tools/hooks/project_memory_hook.py`
- `tools/preview_output.py`
