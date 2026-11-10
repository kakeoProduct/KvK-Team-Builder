---
type: session
id: 2026-11-08T163438Z-review-agents-review-query
title: Review AgentのBashを固定のScriptと閉じた文法に限り、Git保護を2つの判定にする
status: current
created_at: '2026-11-08T16:34:38Z'
base_commit: 4dc45cd3defb53314d480c40fbe2056e937d0eda
final_commit: 4dc45cd3defb53314d480c40fbe2056e937d0eda
tags:
- ai-harness
related_paths:
- .agents/skills/change-ai-harness/references/checklist.md
- .agents/skills/review-kvk-change/SKILL.md
- .agents/skills/review-kvk-change/references/self-check.md
- .claude/agents/kvk-architecture-reviewer.md
- .claude/agents/kvk-domain-reviewer.md
- .claude/agents/kvk-requirements-reviewer.md
- .claude/agents/kvk-test-reviewer.md
- .claude/skills/change-ai-harness/references/checklist.md
- .claude/skills/review-kvk-change/SKILL.md
- .claude/skills/review-kvk-change/references/self-check.md
- .codex/agents/kvk-architecture-reviewer.toml
- .codex/agents/kvk-domain-reviewer.toml
- .codex/agents/kvk-requirements-reviewer.toml
- .codex/agents/kvk-test-reviewer.toml
- .gitignore
- AGENTS.md
- CLAUDE.md
- DEVELOPMENT.md
- docs/adr/0032-verify-web-tools-with-playwright-mcp.md
- docs/adr/0033-limit-review-agent-bash-to-a-fixed-script.md
- docs/adr/README.md
- tests/test_agent_hooks.py
- tests/test_ai_harness.py
- tests/test_preview_output.py
- tests/test_review_query.py
- tools/hooks/block_dangerous_git.py
- tools/hooks/enforce_read_only_agent.py
- tools/preview_output.py
- tools/review_query.py
- tools/sync_agent_config.py
---

# Review AgentのBashを固定のScriptと閉じた文法に限り、Git保護を2つの判定にする

## 利用者の依頼

Review AgentのBashを許可リストの照合から固定のScript（tools/review_query.py）へ移し、実機で確かめ、4担当のレビューの指摘へ対応する

## 実装結果

tools/review_query.pyと閉じた文法のHookを加え、Agent定義、Skill、AGENTS、CLAUDE、DEVELOPMENTとADR 0033をそろえた。Git保護は4dc45cdと同じ判定を先に行い、引用符を解釈する判定（2万文字以下だけ）と厳しいほうを採る方式にした。自己点検リストにC20を足し、C7を見直した

## 重要な判断

- 案Bの維持（利用者の判断、2026-11-06）。Git保護の照合は残す（利用者の判断、2026-11-05）
- Git保護は変更前と同じ判定を必ず行い厳しいほうを採る。引用符の解釈のずれで変更前に止めていた操作を通す回帰が2回続いたため（作成者の判断）
- 引用符を解釈する判定は2万文字以下の入力に限る（利用者の判断、2026-11-08）。値の2万文字は作成者の判断と計測
- 引用符付きのヒアドキュメントの本文はデータとして扱い、区間の最初の語がShellのときと同じ行にShellへのパイプがあるときだけコマンドとして判定する（作成者の判断）
- Agent定義にGrepとGlobを書いても、Bashを持つ担当には渡らない（Claude Code 2.1.318の実機確認。1回の実行からの推定）

## 検証

- python tools/check.py: 成功
- 4担当のレビュー: 初回と再レビュー11回。最新はMustとShouldなし（tmp/reviews/review-agents-without-bash.md）
- Hookの写しから処理を1つずつ外した32の版でテストが失敗することを確認。再現の入力29件で4dc45cdより緩い判定0件

## 未完了事項

- 最新のdevを取り込んだ後の最後の再レビュー
- PR #10のmerge後にdevへPull Requestを作る。自己点検リストの出所をPR番号へ置き換える
- Skillの「振り返る」で、確かめる内容を変えない修正を見直しに数えない案（N34）を利用者へ提案済み

## 正本への参照

- `.agents/skills/change-ai-harness/references/checklist.md`
- `.agents/skills/review-kvk-change/SKILL.md`
- `.agents/skills/review-kvk-change/references/self-check.md`
- `.claude/agents/kvk-architecture-reviewer.md`
- `.claude/agents/kvk-domain-reviewer.md`
- `.claude/agents/kvk-requirements-reviewer.md`
- `.claude/agents/kvk-test-reviewer.md`
- `.claude/skills/change-ai-harness/references/checklist.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.claude/skills/review-kvk-change/references/self-check.md`
- `.codex/agents/kvk-architecture-reviewer.toml`
- `.codex/agents/kvk-domain-reviewer.toml`
- `.codex/agents/kvk-requirements-reviewer.toml`
- `.codex/agents/kvk-test-reviewer.toml`
- `.gitignore`
- `AGENTS.md`
- `CLAUDE.md`
- `DEVELOPMENT.md`
- `docs/adr/0032-verify-web-tools-with-playwright-mcp.md`
- `docs/adr/0033-limit-review-agent-bash-to-a-fixed-script.md`
- `docs/adr/README.md`
- `tests/test_agent_hooks.py`
- `tests/test_ai_harness.py`
- `tests/test_preview_output.py`
- `tests/test_review_query.py`
- `tools/hooks/block_dangerous_git.py`
- `tools/hooks/enforce_read_only_agent.py`
- `tools/preview_output.py`
- `tools/review_query.py`
- `tools/sync_agent_config.py`
