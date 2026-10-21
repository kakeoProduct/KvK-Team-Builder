---
type: session
id: 2026-10-19T140908Z-team-building-requirements-round13
title: 回答を問いの対象の順に確かめ、成り立たない指定は問い直して往復を終える
status: current
created_at: '2026-10-19T14:09:08Z'
base_commit: ba925296f3abb55ee1a6591c5c15d49c4a4b10fe
final_commit: ba925296f3abb55ee1a6591c5c15d49c4a4b10fe
tags:
- requirements
- team-building
related_paths:
- docs/requirements/team-building/README.md
- docs/requirements/team-building/formation-rules.md
- docs/requirements/team-building/open-questions.md
- tests/test_repository_scope.py
---

# 回答を問いの対象の順に確かめ、成り立たない指定は問い直して往復を終える

## 利用者の依頼

PR #43の10回目の再レビューの指摘を反映する。対応可否は作成者が判断する

## 実装結果

入力のエラーをほかの指定で変わらない誤りだけにし、それ以外の成り立たない指定は問い直す形に設計し直した。回答の各指定に問いの対象を書き、その順に、残した指定を前提として、まだ確かめていない対象を下限から外して確かめる。示し直した許しはその前提で成り立つので往復が終わる。Validatorは許しの時間帯と指定した人数以上だけを確かめ、下限を満たしたら許しを使わなかったものとして注記する。A-10に3回目の実行までの例を書き、FRM-037の番号の参照の構造テストを強めた

## 重要な判断

- 入力のエラーはほかの指定で変わらない誤りだけとし、それ以外は問い直す

## 検証

- python tools/check.py 成功（116 passed）
- 定義にない番号（⑪）の参照で構造テストが失敗することを確認

## 未完了事項

- 対応後の再レビュー

## 正本への参照

- `docs/requirements/team-building/README.md`
- `docs/requirements/team-building/formation-rules.md`
- `docs/requirements/team-building/open-questions.md`
- `tests/test_repository_scope.py`
