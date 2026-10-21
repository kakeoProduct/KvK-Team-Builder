---
type: session
id: 2026-10-18T075627Z-team-building-requirements
title: KvKチーム編成の要件定義書を追加（#42）
status: current
created_at: '2026-10-18T07:56:27Z'
base_commit: b2bcd4ecdaf067efa2228420d7505941264eb33d
final_commit: b2bcd4ecdaf067efa2228420d7505941264eb33d
tags:
- docs
- requirements
- team-building
related_paths:
- AGENTS.md
- README.md
- docs/adr/0023-team-building-requirements-specification.md
- docs/adr/README.md
- docs/domain-model.md
- docs/requirements/team-building/README.md
- docs/requirements/team-building/formation-rules.md
- docs/requirements/team-building/open-questions.md
- docs/requirements/team-building/output-and-screen.md
- docs/requirements/team-building/roster-input.md
- tests/test_repository_scope.py
---

# KvKチーム編成の要件定義書を追加（#42）

## 利用者の依頼

利用者の2つの運用ルール文書（同盟メンバー表の整形ルール、チーム編成ロジック）を、要件定義書としてRepositoryに保持する

## 実装結果

docs/requirements/team-building/に総則（用語、現行との差分D-001〜011、実装Issueの分割案）、入力（ROS）、編成ルール（FRM、必須条件・警告・目的関数・運用操作に分類）、出力と画面（OUT、UI）、未決事項（Q-001〜011）を追加。ADR 0023で目標仕様の正本と定め、AGENTS、README、domain-model、ADR索引に導線を追加。要件IDの重複と索引を検査する構造テストを追加

## 重要な判断

- 要件定義書を目標仕様の正本とし、README・AGENTSの現行ルールは実装Issueの完了ごとに置き換える（正本の一時的な二重化をAGENTSの注記で明示）
- 運用値と実運用の参加者名は文書へ書かず設定として持つ。例は架空の名前にした
- 元文書の新旧が食い違う箇所は新しい方を採用し、確定できない点は未決事項に分けた

- 未決事項への回答（2026-10-18）を反映: 出撃人数はリーダー込み8人（7人の例外なし）、8〜10人は各時間帯の出撃人数、戦力は平均Gで第1隊 > 第2隊 > 第3隊 >= 第4隊、上位隊の常時稼働の例外はリーダーだけ、優先順位は上から順で結果は毎回同じ、総力モードは1グループ6隊、警告はテキストと画面の両方、24時以降は24:30表記、スクリーンショット読み取りは任意、協力者は総力の合計だけ、◯最低×4分は治療時間の目安として合計表示に入れる（未決事項は0件）

## 検証

- python tools/check.py: 成功
- 新しい文書に実運用の参加者名が含まれないことをgrepで確認

## 未完了事項

- PR作成（利用者の指示待ち）、その後に実装Issueの作成

## 正本への参照

- `AGENTS.md`
- `README.md`
- `docs/adr/0023-team-building-requirements-specification.md`
- `docs/adr/README.md`
- `docs/domain-model.md`
- `docs/requirements/team-building/README.md`
- `docs/requirements/team-building/formation-rules.md`
- `docs/requirements/team-building/open-questions.md`
- `docs/requirements/team-building/output-and-screen.md`
- `docs/requirements/team-building/roster-input.md`
- `tests/test_repository_scope.py`
