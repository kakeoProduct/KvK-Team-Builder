---
type: promotion-candidate
id: ai-harness-change-procedure
title: AIハーネス変更時の整合手順
status: promoted
target: skill
evidence:
  - 2026-07-20T133550Z-project-memory-and-promotion
  - 2026-07-20T134853Z-review-decision-levels
  - 2026-07-20T154028Z-20260720t153401z-ea877630
  - 2026-08-11T073050Z-install-mattpocock-skills
  - 2026-08-11T075714Z-localize-codex-skills
  - 2026-10-15T094201Z-agent-hooks-and-skill-cleanup
promoted_to: .agents/skills/change-ai-harness/SKILL.md
---

# AIハーネス変更時の整合手順

## 観測した反復

`ai-harness`タグの7件のうち、Dev Container以外の6件はSkill、Review Agent、Hookを追加または
変更するSessionだった。いずれも、正本の変更に加えて同じ周辺ファイルを毎回手作業でそろえている。

- `tests/test_ai_harness.py`の構造テストと期待集合（6件すべて）
- `docs/adr/`の新規ADRと`docs/adr/README.md`の索引（4件）
- `AGENTS.md`と`DEVELOPMENT.md`のSkill一覧と説明（4件）
- 外部Skillの管理対象を外すときの`skills-lock.json`（3件）
- Claude Code対応後は`python tools/sync_agent_config.py`による生成物の同期

漏れが品質ゲートで初めて見つかる失敗も繰り返している。2026-10-15のSessionでは、Codex用Skillへ
`.claude`のパスを書いて既存テストに失敗し、外部Skillをローカルで書き換えるか管理対象から外すかを
改めて判断した。同じ判断は2026-08-11の`localize-codex-skills`でも行っている。

## 昇格案

Repository固有Skill`$change-ai-harness`を追加し、Skill、Review Agent、Hookの追加・変更・削除を
対象にする。`$change-kvk-rules`と同じく、次を一貫させる手順とする。

1. 変更対象を分類する（Repository固有Skill、外部Skill、Review Agent、Hook、Codex専用）
2. 正本（`.agents/skills/`、`.codex/agents/`、`tools/hooks/`）だけを編集する
3. 外部Skillを変更する場合は、ローカルで書き換えず`skills-lock.json`の管理対象から外し、
   Repository固有Skillとして日本語化する
4. `tests/test_ai_harness.py`の期待集合と、振る舞いのテストを先に更新する
5. `AGENTS.md`、`DEVELOPMENT.md`、`CLAUDE.md`のうち該当箇所と、必要ならADRを更新する
6. `python tools/sync_agent_config.py`と`python tools/check.py`を実行する

詳細なチェック項目は`references/`へ分け、`SKILL.md`を短く保つ。

## 昇格条件

- 独立した複数セッションの根拠、または利用者の明示的な昇格依頼がある
- 既存の正本やSkillと責務が重複しない（外部Skill`writing-for-agents`は文章の書き方、
  本候補はRepository内の整合手順を扱う）
- 入力、手順、期待結果、失敗時の扱いを検証できる
- 秘密情報と個人情報を含まない
