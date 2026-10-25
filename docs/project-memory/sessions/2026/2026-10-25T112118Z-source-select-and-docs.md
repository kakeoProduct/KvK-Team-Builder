---
type: session
id: 2026-10-25T112118Z-source-select-and-docs
title: リリースのレビューのShouldへの対応（計算元の選択と要件の補記）
status: current
created_at: '2026-10-25T11:21:18Z'
base_commit: ea5039d7d099d57732c6775558e96eecfd79c32a
final_commit: ea5039d7d099d57732c6775558e96eecfd79c32a
tags:
- review
- web-tools
related_paths:
- docs/requirements/web-tools/siege-timeline.md
- docs/requirements/web-tools/wave-timer.md
- tests/web/helpers.js
- tests/web/siege-properties.js
- tests/web/siege-timeline.test.js
- tests/web/wave-timer.test.js
- web/周期ウェーブタイマー.html
- web/攻城タイムライン計算.html
---

# リリースのレビューのShouldへの対応（計算元の選択と要件の補記）

## 利用者の依頼

リリースのレビュー（dev→main）の2回目のShould S1〜S6をすべて直してから出す

## 実装結果

周期ウェーブタイマーで選び直した計算元を保存の通知で保ち、表示中のタブが別のブラウザのタブで削除されたときは選び直すようにした。KI-SIEGE-02をSIEGE-034へ上げ、移行が一方向であることと#6の細部を7章へ書き、KI-WAVE-14を記録した。削りを選んでいないパターンの固定例と乱数100件、タブのキーボード操作と番号のテストを足した

## 重要な判断

- WAVE-074: 別のタブを表示したときは読み込み済み→直前の選択→先頭、表示中のタブのまま保存データが変わったときは選択を保つ→読み込み済み→先頭とした（作成者の仮定）
- 空のパターンを許す乱数は別のSeed（2468）で作り、既存の1000件の入力を変えない

## 検証

- python tools/check.py成功。変異2件で検査の失敗を確認。Chromium 130で既存23件と計算元の選択8件が成功。4担当のレビューを2回の再レビューまで行い、Must、Shouldなし

## 未完了事項

- リリースのPull Request（dev→main）を、この変更をdevへ取り込んだ後に作り、初回のレビューをやり直す。本文で開いているページの再読み込みを周知する
- Nice: 別のタブを表示したときに直前の選択を保つ経路と、開き直した後のタブ番号の検査

## 正本への参照

- `docs/requirements/web-tools/siege-timeline.md`
- `docs/requirements/web-tools/wave-timer.md`
- `tests/web/helpers.js`
- `tests/web/siege-properties.js`
- `tests/web/siege-timeline.test.js`
- `tests/web/wave-timer.test.js`
- `web/周期ウェーブタイマー.html`
- `web/攻城タイムライン計算.html`
