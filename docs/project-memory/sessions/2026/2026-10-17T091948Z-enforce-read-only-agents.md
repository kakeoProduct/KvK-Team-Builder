---
type: session
id: 2026-10-17T091948Z-enforce-read-only-agents
title: Review Agentの読み取り専用をPreToolUse Hookで強制
status: current
created_at: '2026-10-17T09:19:48Z'
base_commit: dc848bb99a0a52c06d283069704617b63604ed66
final_commit: dc848bb99a0a52c06d283069704617b63604ed66
tags:
- agent-hooks
- ai-harness
related_paths: []
---

# Review Agentの読み取り専用をPreToolUse Hookで強制

## 利用者の依頼

親SessionがautoなどのときSubagentのpermissionMode: planが無視されるため、Review Agentへ読み取り専用を適用したい

## 実装結果

tools/hooks/enforce_read_only_agent.pyを.claude/settings.jsonへ全Tool対象で登録した。agent_typeが.codex/agentsでsandbox_mode=read-onlyのAgentだけに、読み取りTool、内部Tool、許可したBashコマンドを通す。変更パス: tools/hooks/enforce_read_only_agent.py、.claude/settings.json、tests/test_agent_hooks.py、tests/test_ai_harness.py、docs/adr/0018-enforce-read-only-agents-with-hook.md、AGENTS.md、CLAUDE.md、DEVELOPMENT.md、change-ai-harnessのchecklist

## 重要な判断

- Subagent定義のFrontmatterへ書いたHookは新しいSessionでも発火しなかったため、settings.jsonに登録した（ADR 0018）
- SubagentHandbackを拒否すると報告が届かないため、書き込みを伴わない内部Toolを許可した
- preview_output.pyは前回出力を上書きするためReview Agentから実行させない
- 共有記憶の開始状態は先行するfinishで使い切っていたため、新しい開始状態から--forceで記録した

## 検証

- 新しいSessionで、HookがSubagentのSubagentHandbackを独自の文言で拒否し、agent_typeによる判定と発火を確認した
- python -m pytest tests/test_agent_hooks.py: 15件成功
- python tools/check.py: 成功
- 新しいSessionで、kvk-test-reviewerの`python -c "print(1)"`がHookに拒否され、拒否後も結果が返ることを確認した

## 未完了事項

- 未完了なし

## 正本への参照

- 利用者による明示的な記録依頼
