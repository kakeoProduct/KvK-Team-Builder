---
type: session
id: 2026-10-17T123159Z-web-tools-requirements
title: web補助ツールの要件定義書を追加
status: current
created_at: '2026-10-17T12:31:59Z'
base_commit: 4e266559c9ca494f18c7165c2a63501bec5129fd
final_commit: 4e266559c9ca494f18c7165c2a63501bec5129fd
tags:
- docs
- web-tools
related_paths:
- AGENTS.md
- README.md
- docs/adr/0020-web-tools-requirements-specification.md
- docs/adr/README.md
- docs/architecture.md
- docs/requirements/web-tools/README.md
- docs/requirements/web-tools/occupation-judge.md
- docs/requirements/web-tools/siege-timeline.md
- docs/requirements/web-tools/sync-start-tables.md
- docs/requirements/web-tools/voice-stopwatch.md
- docs/requirements/web-tools/wave-timer.md
- tests/test_repository_scope.py
---

# web補助ツールの要件定義書を追加

## 利用者の依頼

webに配置しているツールを修正する前に、要件を要件定義書としてdocsへ保持したい

## 実装結果

docs/requirements/web-tools/に総則・共通要件と5文書（6ツール分）を作成し、ADR 0020、README・architecture・AGENTSの導線、web/*.htmlの掲載を確かめる構造テストを追加

## 重要な判断

- 要件の正本は要件定義書、実装の正本はHTMLとし、食い違いは利用者が判断して同じ変更でそろえる（ADR 0020）
- 初版は現行HTMLのコード読解から書き起こし、意図と異なる振る舞いを既知の不具合（KI-）、意図不明を未決事項（Q-）へ分けた

## 検証

- python tools/check.py: 成功（89 passed）

## 未完了事項

- ブラウザでの現行動作の確認は未実施。未決事項（Q-）の決定と、修正対象の選定は利用者の判断待ち

## 正本への参照

- `AGENTS.md`
- `README.md`
- `docs/adr/0020-web-tools-requirements-specification.md`
- `docs/adr/README.md`
- `docs/architecture.md`
- `docs/requirements/web-tools/README.md`
- `docs/requirements/web-tools/occupation-judge.md`
- `docs/requirements/web-tools/siege-timeline.md`
- `docs/requirements/web-tools/sync-start-tables.md`
- `docs/requirements/web-tools/voice-stopwatch.md`
- `docs/requirements/web-tools/wave-timer.md`
- `tests/test_repository_scope.py`
