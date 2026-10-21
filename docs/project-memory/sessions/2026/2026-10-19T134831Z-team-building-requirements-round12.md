---
type: session
id: 2026-10-19T134831Z-team-building-requirements-round12
title: 24時より前の休止を8人未満に数え、指定の確かめ方を往復で終わる形にする
status: current
created_at: '2026-10-19T13:48:31Z'
base_commit: dfdeee48228b5dea6f283f5b9301fca10b00653c
final_commit: dfdeee48228b5dea6f283f5b9301fca10b00653c
tags:
- requirements
- team-building
related_paths:
- docs/requirements/team-building/README.md
- docs/requirements/team-building/formation-rules.md
- docs/requirements/team-building/open-questions.md
- docs/requirements/team-building/output-and-screen.md
- tests/test_repository_scope.py
---

# 24時より前の休止を8人未満に数え、指定の確かめ方を往復で終わる形にする

## 利用者の依頼

PR #43の9回目の再レビューの指摘を反映する。対応可否は作成者が判断する

## 実装結果

目的関数①のアとウに休止を含め、24時より前でも7人の代わりに休止を選ばないようにした。Validatorは編成から読み取れる事実だけを確かめ、最適化に頼る範囲の確認はアプリケーションへ移した。許したときの人数は問い合わせで示して指定に含める。回答の指定は決まった順に確かめ、同時に成り立たない指定は数え直して問い合わせ直す。判定に使う編成で最適性を示せなければ時間切れのエラーとする。FRM-037の番号の参照を構造テストで確かめる

## 重要な判断

- 回答の8人未満には休止を含む（旧Q-091を文字どおり読む）
- 許したときの人数は指定に含め、アプリケーションが計算し直して一致を確かめる

## 検証

- python tools/check.py 成功（116 passed）
- 定義にない指標の番号への参照で構造テストが失敗することを確認

## 未完了事項

- 対応後の再レビュー

## 正本への参照

- `docs/requirements/team-building/README.md`
- `docs/requirements/team-building/formation-rules.md`
- `docs/requirements/team-building/open-questions.md`
- `docs/requirements/team-building/output-and-screen.md`
- `tests/test_repository_scope.py`
