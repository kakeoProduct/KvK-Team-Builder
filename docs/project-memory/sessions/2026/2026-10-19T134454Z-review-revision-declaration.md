---
type: session
id: 2026-10-19T134454Z-review-revision-declaration
title: 見直しの判定を作成者の申告で決め、ほかのPull Requestの案の読み先を決める
status: current
created_at: '2026-10-19T13:44:54Z'
base_commit: 6db156a828eca4d6d31e4a4250c3e85e13c8c19a
final_commit: 6db156a828eca4d6d31e4a4250c3e85e13c8c19a
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
- tests/test_ai_harness.py
- tests/test_review_fingerprint.py
---

# 見直しの判定を作成者の申告で決め、ほかのPull Requestの案の読み先を決める

## 利用者の依頼

PR #44の9回目の再レビューのShouldとNiceを、作成者の判断で対応する

## 実装結果

前回の振り返りの案（C1、C2、C3、C7、C9、C10、C14の追記と、#43の用語の注記）を最初に反映した。見直したかどうかは作成者の申告で決め、差分は照合に使う。リストがないブランチの案は、そのPull Requestの最新のレビュー結果から読む。記録先の表で、節を作るのは要件定義書だけとし、ハーネスはADRを作る場合に限り、Pull Requestがない場合は作成時に本文へ書く。表の行の数と新しい規則をテストで照合した

## 重要な判断

- 見直したかどうかの正本は作成者の申告とする（コミットせずに再レビューを重ねるとheadが動かないため）

## 検証

- python tools/check.py 成功
- 今回の規則を1か所ずつ戻すとテストが失敗することを8件で確認

## 未完了事項

- 対応後の再レビュー

## 正本への参照

- `.agents/skills/create-github-pr/SKILL.md`
- `.agents/skills/implement/SKILL.md`
- `.agents/skills/review-kvk-change/SKILL.md`
- `.agents/skills/review-kvk-change/references/self-check.md`
- `.claude/skills/create-github-pr/SKILL.md`
- `.claude/skills/implement/SKILL.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.claude/skills/review-kvk-change/references/self-check.md`
- `tests/test_ai_harness.py`
- `tests/test_review_fingerprint.py`
