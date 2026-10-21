---
name: change-ai-harness
description: このRepositoryのSkill、Review Agent、Agent Hookを追加・変更・削除するときに、正本、生成物、テスト、規約文書、ADRを一貫させる。外部Skillの導入や管理対象からの除外、Codex専用Skillの扱い、Hook Scriptの変更時にも使用する。Skillの文章の書き方だけを相談する場合は`$writing-for-agents`を使用する。
---

<!-- このファイルは tools/sync_agent_config.py が.agents/skills/change-ai-harness/SKILL.mdから生成します。直接編集せず、正本を変更してから同期してください。 -->

# AIハーネスを変更する

Skill、Review Agent、Hookの変更を、正本だけで完結させず、同期生成物、構造テスト、規約文書まで
同じ変更でそろえる。漏れは品質ゲートで初めて見つかることが多いため、編集前に影響範囲を確定する。

## 変更対象を分類する

依頼を次から選ぶ。複数に該当する場合はすべて扱う。

- Repository固有Skill: `.agents/skills/<name>/`（説明と本文は日本語）
- 外部Skill: `skills-lock.json`で管理する導入済みSkill
- Review Agent: `.codex/agents/*.toml`
- Agent Hook: `tools/hooks/`のScriptと`.claude/settings.json`
- Codex専用Skill: `tools/sync_agent_config.py`の`CODEX_ONLY_SKILLS`に含めるSkill

## 正本だけを編集する

- `.claude/skills/`と`.claude/agents/`は生成物であり、直接編集しない
- Git保護など両Agentで使うHook Scriptは`tools/hooks/`を正本とし、Skill内へ複製しない
- 外部Skillをローカルで書き換えない。方針と矛盾する場合は`skills-lock.json`の管理対象から
  外し、Repository固有Skillとして日本語化する
- 使わない外部Skillは、暗黙起動の禁止ではなく削除を優先する

## テストを先に更新する

`tests/test_ai_harness.py`の期待集合（`EXPECTED_PROJECT_SKILLS`、`EXPLICIT_ONLY_PROJECT_SKILLS`、
`CODEX_ONLY_SKILLS`など）と、追加する振る舞いのテストを先に変更して失敗を確認する。Hookの判定は
`tests/test_agent_hooks.py`、`tools/`の新しい実行Scriptは`tests/test_tool_output_encoding.py`で
自動的に検査される。

## 文書をそろえる

- 規約に関わる場合は`AGENTS.md`、Claude Code固有の読み替えは`CLAUDE.md`
- Skill一覧と利用方法は`DEVELOPMENT.md`、作業経路の案内は`$choose-skill`
- 方針や依存境界を変える場合は`docs/adr/`へADRを追加し、`docs/adr/README.md`の索引を更新する

項目ごとの確認は[references/checklist.md](references/checklist.md)を使用する。

## 検証する

```text
python tools/sync_agent_config.py
python tools/check.py
```

同期後は正本と生成物の両方を差分に含める。変更Sessionの記録は`$maintain-project-memory`に従う。
