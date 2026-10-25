---
type: session
id: 2026-10-22T101851Z-ci-dedupe-triggers
title: CIのトリガー重複を除き、Pull Requestの古い実行を中止する
status: current
created_at: '2026-10-22T10:18:51Z'
base_commit: 4428193258fbe6a8ad014c4edab93ae0e94aa521
final_commit: 4428193258fbe6a8ad014c4edab93ae0e94aa521
tags:
- ci
- github-actions
related_paths:
- .github/workflows/tests.yml
- DEVELOPMENT.md
- docs/adr/0027-separate-dev-and-main-branches.md
- docs/adr/0028-run-ci-once-per-change.md
- docs/adr/README.md
- tests/test_ai_harness.py
---

# CIのトリガー重複を除き、Pull Requestの古い実行を中止する

## 利用者の依頼

CIの数を適切に絞りたい。一般的な構成とこのRepositoryの最適解を調査し、行列は維持してトリガーの重複だけを除く案（推奨1）を実施する

## 実装結果

品質チェックのpushをmainとdevに限定し、pull_requestは全件のままにした。concurrencyのgroupをPull Requestの番号（pushはrun_id）にし、cancel-in-progressを有効にした。ADR 0028を新設し、ADR 0027の該当点を置き換えた。DEVELOPMENT.mdのブランチ運用と構造テストを更新した。作業branchのPull Requestのチェックは8つから4つになる

## 重要な判断

- 行列（ubuntu/windows × Python 3.11/3.12）4つのjobとjob名は維持し、branch保護の必須チェックは設定し直さない
- concurrencyのgroupは公式文書の例のgithub.head_refではなくgithub.event.pull_request.numberにした。head_refはbranch名だけのため、forkや同じ名前のbranchのPull RequestがリリースPull RequestのCIを中止し得るとレビューで分かり、利用者が同意した
- devへのpush、リリースPull Request、取り込んだ後のmainへのpushは同じ内容を検証するため、リリースごとに3回実行される重複は残す
- （作成者の仮定）Pull Requestを作る前は手元のpython tools/check.pyで確かめ、CIで確かめたい場合は利用者が明示したときに$create-github-prでDraft Pull Requestを作る

## 検証

- python tools/check.py: 成功（189 passed）
- $review-kvk-change: 初回と2回の再レビューを経て承認候補（Must・Shouldなし、Nice 4件は任意）

## 未完了事項

- 取り込んだ後の最初のPull Requestで、続けてpushしたときに古い実行がCancelledになり、mainとdevへのpushの実行は中止されないことを利用者が確かめる
- レビューの任意のNice 4件（判断の箇条の照合、作業PRとdevへのpushの重複の記載、ADR 0027への重複の一言、同じ先頭コミットの言い方）

## 正本への参照

- `.github/workflows/tests.yml`
- `DEVELOPMENT.md`
- `docs/adr/0027-separate-dev-and-main-branches.md`
- `docs/adr/0028-run-ci-once-per-change.md`
- `docs/adr/README.md`
- `tests/test_ai_harness.py`
