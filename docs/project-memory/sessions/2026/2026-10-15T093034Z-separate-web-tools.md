---
type: session
id: 2026-10-15T093034Z-separate-web-tools
title: web/をPython処理の対象外として明文化
status: current
created_at: '2026-10-15T09:30:34Z'
base_commit: 78ce31a2d22e53327d930e86cdaa30ffbf611c66
final_commit: 78ce31a2d22e53327d930e86cdaa30ffbf611c66
tags:
- scope
- web
related_paths:
- README.md
- docs/adr/0013-separate-web-tools-from-python-scope.md
- docs/adr/README.md
- docs/architecture.md
- pyproject.toml
- tests/test_repository_scope.py
---

# web/をPython処理の対象外として明文化

## 利用者の依頼

web/のHTMLロジックを正としてPythonと突き合わせ、方針Aで整理する

## 実装結果

HTMLとPythonに一致する処理がないことを確認し、web/を独立ツールとしてREADME、architecture、ADR 0013に明記した。Ruffのextend-excludeへwebを追加し、品質ゲートが成功するようにした

## 重要な判断

- web/の計算ロジックは各HTMLを正本とし、Pythonへ移植しない

## 検証

- python tools/check.py: 成功（pytest 44件）

## 未完了事項

- ADR 0013を採用へ更新
- 周期ウェーブタイマーが①〜⑩以外のパターン見出しを直前パターンへ混ぜる不具合など、HTML側の不具合は未修正

## 正本への参照

- `README.md`
- `docs/adr/0013-separate-web-tools-from-python-scope.md`
- `docs/adr/README.md`
- `docs/architecture.md`
- `pyproject.toml`
- `tests/test_repository_scope.py`
