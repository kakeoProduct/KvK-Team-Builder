---
type: session
id: 2026-10-15T092436Z-support-codex-and-claude-code
title: CodexとClaude Codeの両対応
status: current
created_at: '2026-10-15T09:24:36Z'
base_commit: 78ce31a2d22e53327d930e86cdaa30ffbf611c66
final_commit: 78ce31a2d22e53327d930e86cdaa30ffbf611c66
tags:
- agents
- claude-code
- codex
related_paths: []
---

# CodexとClaude Codeの両対応

## 利用者の依頼

RepositoryをClaudeでもCodexでも開発を続けられるように整理する

## 実装結果

CLAUDE.mdでAGENTS.mdを取り込み、tools/sync_agent_config.pyで.agents/skillsと.codex/agentsから.claude/skillsと.claude/agentsを生成し、品質ゲートで同期漏れを検出するようにした。Dev ContainerへClaude Code拡張機能を追加し、ADR 0012と開発ガイドを更新した

## 重要な判断

- 正本はCodex向け構成のまま維持し、Windowsでのsymlink依存を避けるため生成物をGit管理する
- Codex専用Skill(codex-handoff, git-guardrails-codex)とopenai.yamlはClaude Codeへ複製せず、暗黙起動禁止はdisable-model-invocationへ変換する

## 検証

- 同期--check、Ruff lint、mypy、pytest 43件: 成功
- Ruff formatはweb/work/inject_sidebar.pyの既存未整形により失敗（今回の変更外）

## 未完了事項

- web/work/inject_sidebar.pyの整形とLint修正
- ADR 0012を採用へ更新
- セッション開始時にPyYAML未導入でstartが失敗したため、変更パスは--forceで記録

## 正本への参照

- 利用者による明示的な記録依頼
