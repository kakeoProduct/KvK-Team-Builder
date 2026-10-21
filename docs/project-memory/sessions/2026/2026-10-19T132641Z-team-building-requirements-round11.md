---
type: session
id: 2026-10-19T132641Z-team-building-requirements-round11
title: 24時より前の8人未満を休止より先に比べ、選択肢の判定を往復しても一つに決める
status: current
created_at: '2026-10-19T13:26:41Z'
base_commit: 18c11696a176be71312d7ef759e90b0d65d682fb
final_commit: 18c11696a176be71312d7ef759e90b0d65d682fb
tags:
- requirements
- team-building
related_paths:
- docs/requirements/team-building/README.md
- docs/requirements/team-building/formation-rules.md
- docs/requirements/team-building/open-questions.md
- tests/test_repository_scope.py
---

# 24時より前の8人未満を休止より先に比べ、選択肢の判定を往復しても一つに決める

## 利用者の依頼

PR #43の8回目の再レビューの指摘と確認事項1件の回答（選ばない）を要件へ反映する。ほかの指摘の対応可否は作成者が判断する

## 実装結果

旧Q-091を記録し、目的関数の①を延長境界時刻より前の8人未満、休止、以降の8人未満の順に比べる形にした。遅れて出撃させる案は同じ問い合わせのほかの不足を除いて数え、解がない場合の判定の編成、指定の範囲の確かめ方、隊数を減らす指定の適用順、明示して許した人数の下限、応援先を指定したメンバーの所属を決めた。戦闘時間を通して0人のFIXの隊は6人以下として扱う。A-12を取り下げてA-13〜A-16を加え、仮定の参照の構造テストが空振りしないようにした

## 重要な判断

- 24時以降の休止を減らすために24時より前の7人を増やさない（旧Q-091）
- 戦闘時間を通して0人のFIXの隊は出撃しない状態を作らず、序盤の6人以下として扱う

## 検証

- python tools/check.py 成功（116 passed）
- 取り下げた仮定、存在しない仮定、記号の後の参照、参照されない仮定の4通りで構造テストが失敗することを確認

## 未完了事項

- 対応後の再レビュー

## 正本への参照

- `docs/requirements/team-building/README.md`
- `docs/requirements/team-building/formation-rules.md`
- `docs/requirements/team-building/open-questions.md`
- `tests/test_repository_scope.py`
