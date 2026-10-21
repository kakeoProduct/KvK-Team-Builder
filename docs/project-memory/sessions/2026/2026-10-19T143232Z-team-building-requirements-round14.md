---
type: session
id: 2026-10-19T143232Z-team-building-requirements-round14
title: 回答の確かめ方を満たすべき性質と例にし、手順は実装Issueで決める
status: current
created_at: '2026-10-19T14:32:32Z'
base_commit: abcddff383660cfbf614680985187d4e403796b6
final_commit: abcddff383660cfbf614680985187d4e403796b6
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

# 回答の確かめ方を満たすべき性質と例にし、手順は実装Issueで決める

## 利用者の依頼

PR #43の11回目の再レビューの指摘を反映する。利用者は、回答の確かめ方を要件では結果だけにすることを選んだ

## 実装結果

FRM-090の手順の記述を、6つの性質（示した選択肢で答えれば入力のエラーにならない、問い直しは決まらない対象だけ、受け入れた指定を前提に表とFRM-041に従う、往復のたびに決まる対象が増える、同じ入力なら同じ結果、回答を確かめる探索も時間切れのエラー）と受け入れの例に置き換えた。隊数を減らす指定は数を持たず確かめる時点で計算し、入力のエラーの一覧から外した。問いの対象を持たない指定の矛盾、画面の経路の確認、使わなかった指定の注記の出力先、出撃開始前になった許しを決めた。FRM-037の定義の検査を、参照を除いた出現順にした

## 重要な判断

- 回答を確かめる手順の細部は実装Issue（分割案の2と4）でテストとADRとともに決める（利用者が選択）

## 検証

- python tools/check.py 成功（116 passed）
- FRM-037の⑩の定義を消すと構造テストが失敗することを確認

## 未完了事項

- 対応後の再レビュー

## 正本への参照

- `docs/requirements/team-building/README.md`
- `docs/requirements/team-building/formation-rules.md`
- `docs/requirements/team-building/open-questions.md`
- `docs/requirements/team-building/output-and-screen.md`
- `tests/test_repository_scope.py`
