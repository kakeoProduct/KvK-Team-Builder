---
type: session
id: 2026-11-05T130722Z-align-hook-parse-failures
title: 安全策のHookの例外処理をそろえ、Review AgentのBashの扱いを別の変更へ分ける
status: current
created_at: '2026-11-05T13:07:22Z'
base_commit: 499757a8da0d78aa54a6ee643fb7dafcd6156d27
final_commit: 499757a8da0d78aa54a6ee643fb7dafcd6156d27
tags:
- ai-harness
related_paths:
- DEVELOPMENT.md
- tests/test_agent_hooks.py
- tools/hooks/block_dangerous_git.py
- tools/hooks/enforce_read_only_agent.py
---

# 安全策のHookの例外処理をそろえ、Review AgentのBashの扱いを別の変更へ分ける

## 利用者の依頼

PR #10で、block_dangerous_git.pyとenforce_read_only_agent.pyのexceptをrestrict_browser_files.pyへそろえる。再レビューの指摘の扱いを判断する

## 実装結果

2つのHookのexceptを(ValueError, RecursionError)へそろえ、語中の#の迂回（S15）と壊れたAgent定義の例外終了（S16）を修正し、文字列でないtool_nameを拒否した。DEVELOPMENT.mdのHook表を実装に合わせた

## 重要な判断

- S17の実装側、S18、S19は既存の動作のため修正せず、利用者の判断（2026-11-05）で見送り、別のPull Requestで扱う
- 別のPull Requestでは、照合の強化ではなくReview AgentからBashを外す案を軸にし、ADR 0018の見直しとして記録する。Git保護は手元の操作を見るため照合を残し、解析できない区間の扱いを直す

## 検証

- python tools/check.py: 成功
- 再レビュー11回目: 承認候補（Mustなし、今回のShouldなし）

## 未完了事項

- S17の実装側、S18、S19、N58、N59、N65を別のPull Requestで扱う。着手前に過去のレビュー担当のBashの使用状況を調べる

## 正本への参照

- `DEVELOPMENT.md`
- `tests/test_agent_hooks.py`
- `tools/hooks/block_dangerous_git.py`
- `tools/hooks/enforce_read_only_agent.py`
