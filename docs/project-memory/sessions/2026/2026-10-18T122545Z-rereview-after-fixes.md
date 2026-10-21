---
type: session
id: 2026-10-18T122545Z-rereview-after-fixes
title: レビュー指摘への対応後に再レビューする
status: current
created_at: '2026-10-18T12:25:45Z'
base_commit: e22706c952fd1689e22f0397d415b14c680cd6aa
final_commit: e22706c952fd1689e22f0397d415b14c680cd6aa
tags:
- ai-harness
- review
related_paths:
- .agents/skills/create-github-pr/SKILL.md
- .agents/skills/implement/SKILL.md
- .agents/skills/review-kvk-change/SKILL.md
- .claude/skills/create-github-pr/SKILL.md
- .claude/skills/implement/SKILL.md
- .claude/skills/review-kvk-change/SKILL.md
- AGENTS.md
- docs/adr/0024-review-document-changes-and-requirements.md
- tests/test_ai_harness.py
---

# レビュー指摘への対応後に再レビューする

## 利用者の依頼

AIレビューの指摘に対応した後は、再度AIレビューを回すようにしたい

## 実装結果

review-kvk-changeの手順5を、対応後の差分に本Skillを再実行し、前回の指摘ごとの対応状況と新たな問題を確かめて新しいコメントで投稿する形に変更。Mustがなくなるか利用者がリスクを受け入れるまで繰り返す。AGENTS、implement、create-github-pr、ADR 0024、構造テストを更新

## 重要な判断

- 対応状況の更新だけでは、対応が指摘を解消したかと対応による新たな問題を確かめられないため、再レビューを必須にした

## 検証

- python tools/check.py: 成功

## 未完了事項

- #44と#43の対応後の再レビュー

## 正本への参照

- `.agents/skills/create-github-pr/SKILL.md`
- `.agents/skills/implement/SKILL.md`
- `.agents/skills/review-kvk-change/SKILL.md`
- `.claude/skills/create-github-pr/SKILL.md`
- `.claude/skills/implement/SKILL.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `AGENTS.md`
- `docs/adr/0024-review-document-changes-and-requirements.md`
- `tests/test_ai_harness.py`
