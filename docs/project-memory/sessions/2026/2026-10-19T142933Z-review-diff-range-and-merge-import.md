---
type: session
id: 2026-10-19T142933Z-review-diff-range-and-merge-import
title: 申告と照らす差分の範囲と、基準ブランチの取り込み方を決める
status: current
created_at: '2026-10-19T14:29:33Z'
base_commit: 95e52cf55bb13da145264158695a731315573b29
final_commit: 95e52cf55bb13da145264158695a731315573b29
tags:
- ai-harness
- review
related_paths:
- .agents/skills/create-github-pr/SKILL.md
- .agents/skills/implement/SKILL.md
- .agents/skills/review-kvk-change/SKILL.md
- .agents/skills/review-kvk-change/references/self-check.md
- .claude/skills/create-github-pr/SKILL.md
- .claude/skills/implement/SKILL.md
- .claude/skills/review-kvk-change/SKILL.md
- .claude/skills/review-kvk-change/references/self-check.md
- docs/adr/0024-review-document-changes-and-requirements.md
- tests/test_ai_harness.py
---

# 申告と照らす差分の範囲と、基準ブランチの取り込み方を決める

## 利用者の依頼

PR #44の11回目の再レビューのShould 5件を直して区切る（利用者が選択）

## 実装結果

前回の振り返りの案（C4の見直し、C5、C7、C9、C11、C13、C14、C15の追記、C1の例の時間の条件、前文の用語）を最初に反映した。申告と照らす差分を前回のheadから作業ツリーまでとし、リストがないブランチでは示したコミットの差分と1回だけ照らす。基準ブランチは利用者の明示を得てmergeで取り込む。反映済みは案の文で確かめる。Pull Requestがある場合の仮定の追記は手順7の方法で承認を得る。自己点検リストの番号の連番をテストで確かめる

## 重要な判断

- 基準ブランチの取り込みはforce pushを要しないmergeとし、利用者の明示を得る

## 検証

- python tools/check.py 成功（135 passed）
- 今回足した14文を1文ずつ消すとテストが失敗することを確認（手順7の追記、差分の範囲、merge、反映済みの確かめ方、写す仮定の範囲、テンプレート、番号の連番を含む）

## 未完了事項

- 対応後の再レビュー（1回で区切る）

## 正本への参照

- `.agents/skills/create-github-pr/SKILL.md`
- `.agents/skills/implement/SKILL.md`
- `.agents/skills/review-kvk-change/SKILL.md`
- `.agents/skills/review-kvk-change/references/self-check.md`
- `.claude/skills/create-github-pr/SKILL.md`
- `.claude/skills/implement/SKILL.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.claude/skills/review-kvk-change/references/self-check.md`
- `docs/adr/0024-review-document-changes-and-requirements.md`
- `tests/test_ai_harness.py`
