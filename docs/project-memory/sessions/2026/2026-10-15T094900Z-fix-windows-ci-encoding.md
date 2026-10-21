---
type: session
id: 2026-10-15T094900Z-fix-windows-ci-encoding
title: Windows CIの日本語出力エラーを修正
status: current
created_at: '2026-10-15T09:49:00Z'
base_commit: 845da6591cf4f536b6894cb521b4d7970d10b13d
final_commit: 845da6591cf4f536b6894cb521b4d7970d10b13d
tags:
- bugfix
- ci
- windows
related_paths:
- .github/workflows/tests.yml
- tests/test_tool_output_encoding.py
- tools/check.py
- tools/sync_agent_config.py
---

# Windows CIの日本語出力エラーを修正

## 利用者の依頼

PR #22のCI失敗を修正する

## 実装結果

Windowsランナーのcp1252 Consoleで日本語出力がUnicodeEncodeErrorになる問題を、CIのPYTHONUTF8=1と、check.pyおよび同期ScriptのUTF-8出力で修正した

## 重要な判断

- CIはUTF-8モードで入出力を統一し、開発ToolはConsoleの文字コードに依存せずUTF-8で出力する

## 検証

- クリーンなworktreeでPYTHONUTF8=1のpython tools/check.py: 成功（46件）
- cp1252を模擬した出力テスト: 成功

## 未完了事項

- 共有記憶ScriptはUTF-8モードなしのcp1252環境で失敗するため、Script側のUTF-8出力化を別途検討

## 正本への参照

- `.github/workflows/tests.yml`
- `tests/test_tool_output_encoding.py`
- `tools/check.py`
- `tools/sync_agent_config.py`
