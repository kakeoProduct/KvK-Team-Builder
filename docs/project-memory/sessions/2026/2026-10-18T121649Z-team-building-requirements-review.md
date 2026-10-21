---
type: session
id: 2026-10-18T121649Z-team-building-requirements-review
title: KvKチーム編成の要件定義書をレビュー指摘と回答で改訂（#43）
status: current
created_at: '2026-10-18T12:16:49Z'
base_commit: cbd6666d47369c9fcc80ec80be44b564a96a1c3c
final_commit: cbd6666d47369c9fcc80ec80be44b564a96a1c3c
tags:
- docs
- requirements
- team-building
related_paths:
- AGENTS.md
- docs/adr/0023-team-building-requirements-specification.md
- docs/architecture.md
- docs/domain-model.md
- docs/requirements/team-building/README.md
- docs/requirements/team-building/formation-rules.md
- docs/requirements/team-building/open-questions.md
- docs/requirements/team-building/output-and-screen.md
- docs/requirements/team-building/roster-input.md
- tests/test_repository_scope.py
---

# KvKチーム編成の要件定義書をレビュー指摘と回答で改訂（#43）

## 利用者の依頼

PR #43の要件レビュー（Must 5件、Should 13件）と、運用者への確認事項16件の回答を要件定義書へ反映する

## 実装結果

所属固定と応援・待機の両立、上限の必須条件化と運用者の上限超えの例外、上位隊のリーダー不在時の7人、遅れて出撃する隊の運用者選択と出撃開始時刻、隊を解散しない方針、平均Gの同点のT11判定、序盤と延長境界時刻の設定値化、目的関数の指標、FRM-038の非機能化、用語表の現行用語との対応、差分表D-013・D-014、分割案の範囲と依存を反映。2回目の決定を旧Q-012〜027、残る未決事項をQ-028〜031とした。構造テストを索引・ID・参照の検査へ強化

## 重要な判断

- 2回目の回答に1回目の番号を流用しかけたため、決定ごとに新しい番号を振った（旧Q-001〜011と旧Q-012〜027）
- 運用値と実運用の同盟名を本文から外し、決めた値は決定済みの事項にだけ記録した

- 3回目の回答を反映: 序盤以外も6人以下は出力不可（FRM-039を新設）、呼び名は照合だけ、★の条件はいる★のうち1人が満たせばよい、延長境界は24:00固定。未決事項は0件

## 検証

- python tools/check.py: 成功
- 構造テストが存在しない要件IDへの参照と、索引にない文書で失敗することを確認

## 未完了事項

- #44のマージ後に#43へmainを取り込み競合を解消する

## 正本への参照

- `AGENTS.md`
- `docs/adr/0023-team-building-requirements-specification.md`
- `docs/architecture.md`
- `docs/domain-model.md`
- `docs/requirements/team-building/README.md`
- `docs/requirements/team-building/formation-rules.md`
- `docs/requirements/team-building/open-questions.md`
- `docs/requirements/team-building/output-and-screen.md`
- `docs/requirements/team-building/roster-input.md`
- `tests/test_repository_scope.py`
