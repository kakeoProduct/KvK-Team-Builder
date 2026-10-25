---
type: session
id: 2026-10-25T085809Z-siege-wave-tabs
title: 集結タイムライン計算と周期ウェーブタイマーのタブ化、周期計算の修正、jsdomの検査
status: current
created_at: '2026-10-25T08:58:09Z'
base_commit: 456055f29e8f8c9e7c1a911158b2599b4d44f7bc
final_commit: 456055f29e8f8c9e7c1a911158b2599b4d44f7bc
tags:
- ci
- web-tools
related_paths:
- .devcontainer/Dockerfile
- .devcontainer/devcontainer.json
- .github/workflows/tests.yml
- .gitignore
- .node-version
- DEVELOPMENT.md
- README.md
- docs/adr/0013-separate-web-tools-from-python-scope.md
- docs/adr/0026-publish-repository-with-fictional-names.md
- docs/adr/0030-test-web-tools-with-node-and-jsdom.md
- docs/adr/README.md
- docs/architecture.md
- docs/domain-model.md
- docs/requirements/web-tools/README.md
- docs/requirements/web-tools/siege-timeline.md
- docs/requirements/web-tools/wave-timer.md
- package-lock.json
- package.json
- tests/test_dev_container.py
- tests/test_web_tool_checks.py
- tests/web/helpers.js
- tests/web/siege-properties.js
- tests/web/siege-random-1.test.js
- tests/web/siege-random-2.test.js
- tests/web/siege-random-3.test.js
- tests/web/siege-random-4.test.js
- tests/web/siege-random.js
- tests/web/siege-timeline.test.js
- tests/web/wave-timer.test.js
- tools/check.py
- tools/check_web.py
- web/周期ウェーブタイマー.html
- web/攻城タイムライン計算.html
---

# 集結タイムライン計算と周期ウェーブタイマーのタブ化、周期計算の修正、jsdomの検査

## 利用者の依頼

合意済みの計画書（Git管理外）に従い、両ツールにページ内タブと計算元の読み込みを加え、集結タイムライン計算の周期のずれを直し、実物のHTMLをNode.jsとjsdomで動かす検査を品質ゲートへ入れる

## 実装結果

集結タイムライン計算は1周目を定義順に確定し、周期を全員の帰還+バッファを守る最小値、2周目を1周目+周期とした（SIEGE-013、017、021）。メイン0人は計算しない（SIEGE-033）。両ツールにタブ、保存キーsiegeCalcTabs／waveTimerTabsと旧キーからの移行、周期ウェーブタイマーの計算元の読み込みと状態表示、入力変更の注意（SIEGE-043）を加えた。tests/web/がjsdomで性質C1〜C9を1000件で検査し、tools/check_web.pyを品質ゲートへ加え、Node.js 22.11.0とjsdom 25.0.1をDev ContainerとCIへ入れた（ADR 0030）

## 重要な判断

- ADR 0030: 実物のHTMLをNode.jsとjsdomで検査し、Node.jsがなければ入れ方を示して失敗させる。devで0029が使われたため0030へ振り直した
- 利用者の回答（2026-10-25）: 計算できないときは前回の参考結果を残す（KI-SIEGE-02）、新しいタブは表示中のタブを複製、計算後に入力を変えたら注意を表示、周期ウェーブタイマーのタブ名はタイマー{番号}、メンバー0人のタブもそのまま復元する
- （作成者の仮定）計算できなかったときは、残した参考結果があればその入力を引き継いで比べ、なければ注意を出さない。細部は両要件定義書の7章
- （作成者の仮定）周期ウェーブタイマーの予定はsetTimeoutの連鎖でなくスタート時刻からの経過で毎回求め、非表示のタブも計測を続ける
- （作成者の仮定）集結タイムライン計算のタブのidに作った時刻と乱数を含め（SIEGE-041）、周期ウェーブタイマーはidで計算元を見分ける（WAVE-073）。保存データだけが作り直されたときに、同じ名前と版番号の別のタブを読み込み済みと誤表示しないため（利用者の依頼による修正）

## 検証

- python tools/check.py: 成功（pytest 206件、ブラウザ用補助ツールの検査53件）
- $review-kvk-change: 4観点で初回と再レビュー5回。結果はGit管理外のtmp/reviews/

## 未完了事項

- Pull RequestのCI（ubuntu／windows × Python 3.11／3.12）での確認。特にwindows-latestでのnode --testの相対パス
- 作り直したDev Containerでのnode --versionとpython tools/check.pyの確認（この環境にDockerがない）
- 実際のブラウザでのDesktop幅とMobile幅の確認（COM-053）
- mergeは利用者の判断待ち（コミットとDraft Pull Requestの作成は2026-10-25に利用者が依頼）

## 正本への参照

- `.devcontainer/Dockerfile`
- `.devcontainer/devcontainer.json`
- `.github/workflows/tests.yml`
- `.gitignore`
- `.node-version`
- `DEVELOPMENT.md`
- `README.md`
- `docs/adr/0013-separate-web-tools-from-python-scope.md`
- `docs/adr/0026-publish-repository-with-fictional-names.md`
- `docs/adr/0030-test-web-tools-with-node-and-jsdom.md`
- `docs/adr/README.md`
- `docs/architecture.md`
- `docs/domain-model.md`
- `docs/requirements/web-tools/README.md`
- `docs/requirements/web-tools/siege-timeline.md`
- `docs/requirements/web-tools/wave-timer.md`
- `package-lock.json`
- `package.json`
- `tests/test_dev_container.py`
- `tests/test_web_tool_checks.py`
- `tests/web/helpers.js`
- `tests/web/siege-properties.js`
- `tests/web/siege-random-1.test.js`
- `tests/web/siege-random-2.test.js`
- `tests/web/siege-random-3.test.js`
- `tests/web/siege-random-4.test.js`
- `tests/web/siege-random.js`
- `tests/web/siege-timeline.test.js`
- `tests/web/wave-timer.test.js`
- `tools/check.py`
- `tools/check_web.py`
- `web/周期ウェーブタイマー.html`
- `web/攻城タイムライン計算.html`
