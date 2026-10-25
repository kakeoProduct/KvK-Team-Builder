---
type: session
id: 2026-10-25T103033Z-release-review-fixes
title: リリースのレビューで出た集結タイムライン計算と周期ウェーブタイマーの指摘を直す
status: current
created_at: '2026-10-25T10:30:33Z'
base_commit: 9a06c6d8fe6dafe9aa78ba84f78ffabbf4c88ad7
final_commit: 9a06c6d8fe6dafe9aa78ba84f78ffabbf4c88ad7
tags:
- web-tools
related_paths:
- DEVELOPMENT.md
- docs/requirements/web-tools/siege-timeline.md
- docs/requirements/web-tools/wave-timer.md
- tests/web/siege-properties.js
- tests/web/siege-random.js
- tests/web/siege-timeline.test.js
- tests/web/wave-timer.test.js
- web/周期ウェーブタイマー.html
- web/攻城タイムライン計算.html
---

# リリースのレビューで出た集結タイムライン計算と周期ウェーブタイマーの指摘を直す

## 利用者の依頼

dev→mainのリリースのレビューで出たShould 6件を、すべて直してからリリースする（利用者の依頼）

## 実装結果

周期ウェーブタイマーで旧形式から移したタイムラインに注意を出し（WAVE-077）、両ツールで別のブラウザのタブでの保存とページの復元を読み直す（SIEGE-044、WAVE-053）。計測中のタブは計測に使っている設定を表示し、別のブラウザのタブで削除されたら計測を終えたことを知らせる。周期ウェーブタイマーのタブのidを重ならない値にした。性質C10（Tの最小性）と、保存失敗、計算元の状態の名前と判定順の検査を加えた。Chromium 130でDesktop幅とMobile幅の23項目を確かめ、スマホ幅でボタンが折り返す崩れを2つ直した

## 重要な判断

- 利用者の依頼（2026-10-25）: リリースのレビューのShould 6件をすべて直してから出す
- （作成者の仮定）別のブラウザのタブでの保存へは、警告ではなく読み直しで対処し、読み直しの間は保存し直さない（SIEGE-044、WAVE-053）
- （作成者の仮定）旧形式のタイムラインには、リリースでの周知ではなく画面の注意で知らせる（WAVE-077）
- （作成者の仮定）計測中のタブの設定が別のブラウザのタブで変わっても、スタート時の設定で計測を続け、その値を表示する

## 検証

- python tools/check.py: 成功（pytest 206件、ブラウザ用補助ツールの検査73件）
- Chromium 130（Playwright、Container内に権限なしで取得したライブラリ）: 23項目すべて期待どおり
- $review-kvk-change: 4観点で初回と再レビュー2回。最終はMustとShouldなし（承認候補）

## 未完了事項

- このPull Requestを取り込んだ後、dev→mainのリリースのレビューをやり直してリリースPull Requestを作る
- 戻る操作でブラウザがページを復元した経路（pageshowのpersisted）は、jsdomの合成したイベントでだけ確かめた
- レビューのNice（旧形式のidのデータの検査、要件の細部）は未対応

## 正本への参照

- `DEVELOPMENT.md`
- `docs/requirements/web-tools/siege-timeline.md`
- `docs/requirements/web-tools/wave-timer.md`
- `tests/web/siege-properties.js`
- `tests/web/siege-random.js`
- `tests/web/siege-timeline.test.js`
- `tests/web/wave-timer.test.js`
- `web/周期ウェーブタイマー.html`
- `web/攻城タイムライン計算.html`
