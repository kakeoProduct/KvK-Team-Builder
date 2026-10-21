---
type: session
id: 2026-10-15T101300Z-promote-harness-and-utf8
title: 昇格候補2件の昇格
status: current
created_at: '2026-10-15T10:13:00Z'
base_commit: 60b3178a14cddee92ed44929f82c61a1a89bcc51
final_commit: 60b3178a14cddee92ed44929f82c61a1a89bcc51
tags:
- ai-harness
- windows
related_paths:
- .agents/skills/change-ai-harness/SKILL.md
- .agents/skills/change-ai-harness/agents/openai.yaml
- .agents/skills/change-ai-harness/references/checklist.md
- .agents/skills/choose-skill/SKILL.md
- .claude/skills/change-ai-harness/SKILL.md
- .claude/skills/change-ai-harness/references/checklist.md
- .claude/skills/choose-skill/SKILL.md
- AGENTS.md
- DEVELOPMENT.md
- tests/test_ai_harness.py
- tests/test_tool_output_encoding.py
---

# 昇格候補2件の昇格

## 利用者の依頼

昇格候補2件を昇格する

## 実装結果

AIハーネス変更手順を$change-ai-harnessへ、UTF-8入出力をAGENTS.mdのコーディング規約へ昇格し、tools配下の実行Scriptを文字コード検査で自動列挙するようにした

## 重要な判断

- 既存手順の明文化で新しい方針を含まないためADRは追加しない
- UTF-8処理の共通Module化はScriptのsys.path操作が必要になるため見送り、自動列挙テストで追加漏れを防ぐ

## 検証

- python tools/check.py: 成功（65 passed）

## 未完了事項

- 未完了なし

## 正本への参照

- `.agents/skills/change-ai-harness/SKILL.md`
- `.agents/skills/change-ai-harness/agents/openai.yaml`
- `.agents/skills/change-ai-harness/references/checklist.md`
- `.agents/skills/choose-skill/SKILL.md`
- `.claude/skills/change-ai-harness/SKILL.md`
- `.claude/skills/change-ai-harness/references/checklist.md`
- `.claude/skills/choose-skill/SKILL.md`
- `AGENTS.md`
- `DEVELOPMENT.md`
- `tests/test_ai_harness.py`
- `tests/test_tool_output_encoding.py`
