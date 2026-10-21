---
type: session
id: 2026-07-20T133550Z-project-memory-and-promotion
title: 変更Sessionの共有記憶と知識昇格を実装
status: current
created_at: '2026-07-20T13:35:50Z'
base_commit: 60da1c683f9ac90bbe9d7d75613b450a3e3effd3
final_commit: 60da1c683f9ac90bbe9d7d75613b450a3e3effd3
tags:
- ai-harness
- memory
- skill
related_paths:
- .agents/skills/maintain-project-memory/SKILL.md
- .agents/skills/maintain-project-memory/agents/openai.yaml
- .agents/skills/maintain-project-memory/assets/promotion-candidate-template.md
- .agents/skills/maintain-project-memory/assets/session-note-template.md
- .agents/skills/maintain-project-memory/scripts/session_memory.py
- AGENTS.md
- DEVELOPMENT.md
- docs/adr/0006-project-memory-and-promotion.md
- docs/adr/README.md
- docs/project-memory/INDEX.md
- docs/project-memory/README.md
- tests/test_ai_harness.py
---

# 変更Sessionの共有記憶と知識昇格を実装

## 利用者の依頼

機能作成またはRepository変更が発生したSessionを記憶し、反復した知識をSkillなどへ昇格できる
仕組みを実装する。

## 実装結果

変更前後のGit状態を比較して対象Sessionだけを記録する`$maintain-project-memory`、人間が読める
共有記憶と生成索引、昇格候補Lifecycle、ADR、運用文書、回帰Testを追加した。

## 重要な判断

- 会話全文ではなく、依頼、結果、変更パス、判断、検証、未完了事項だけをGitへ保存する
- 開始時状態はOSの一時Directoryへ置き、開始前から存在する利用者差分と共有記憶自身を除外する
- 反復知識の候補検出と実昇格を分け、実昇格には利用者の承認または明示的な依頼を必要とする
- 昇格後はSkill、AGENTS.md、ADRなどの昇格先を正本とし、元の記憶は来歴として残す
- Local Memory、Database、Vector検索へ必須規約を依存させず、MarkdownとPython Scriptで開始する

## 検証

- `python -m pytest tests/test_ai_harness.py -q`: 5件成功
- `quick_validate.py .agents/skills/maintain-project-memory`: 成功
- `session_memory.py validate`: 成功
- `python tools/check.py`: Ruff、mypy、pytest 30件すべて成功

## 未完了事項

- なし

## 正本への参照

- `AGENTS.md`
- `.agents/skills/maintain-project-memory/SKILL.md`
- `docs/project-memory/README.md`
- `docs/adr/0006-project-memory-and-promotion.md`
- `tests/test_ai_harness.py`
