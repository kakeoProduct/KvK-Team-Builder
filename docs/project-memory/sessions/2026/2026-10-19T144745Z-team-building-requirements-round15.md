---
type: session
id: 2026-10-19T144745Z-team-building-requirements-round15
title: 回答を受けた実行の性質の語を定義し、検証方法と例を足す
status: current
created_at: '2026-10-19T14:47:45Z'
base_commit: 81516d1a214f56e95c85c32d395cf8fa3cee24d3
final_commit: 81516d1a214f56e95c85c32d395cf8fa3cee24d3
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

# 回答を受けた実行の性質の語を定義し、検証方法と例を足す

## 利用者の依頼

PR #43の12回目の再レビューのShould 10件を直して区切る（利用者が選択）

## 実装結果

FRM-090の性質に、決まった（隊、時間帯）の定義、前提（参加者一覧と設定を変えない）、例外（時間切れと入力のエラー）、往復の回数の上限、同じ入力の範囲と回答の順によらないこと、最後の出力はFRM-049に従うことを書いた。場合1の参照を表に直し、対象自身の指定で直った場合は注記しない。隊数を減らす選択肢は必須条件を満たす場合だけ示し、同じ回答の許しを数える。回答以外の指定の矛盾の範囲と判定を決めた。旧Q-092を記録し、A-10に例3と例4を足し、FRM-038と分割案の3、4に性質のテストを書いた

## 重要な判断

- 回答の確かめ方は要件では性質と例だけにする（旧Q-092）

## 検証

- python tools/check.py 成功（116 passed）
- FRM-037の⑩の定義を消すと、また⑪を参照すると構造テストが失敗することを確認

## 未完了事項

- 対応後の再レビュー（1回で区切る）

## 正本への参照

- `docs/requirements/team-building/README.md`
- `docs/requirements/team-building/formation-rules.md`
- `docs/requirements/team-building/open-questions.md`
- `docs/requirements/team-building/output-and-screen.md`
- `tests/test_repository_scope.py`
