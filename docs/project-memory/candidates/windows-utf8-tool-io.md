---
type: promotion-candidate
id: windows-utf8-tool-io
title: 開発ToolとHookの入出力をUTF-8へ固定する
status: promoted
target: agents-guidance
evidence:
  - 2026-10-15T094201Z-agent-hooks-and-skill-cleanup
  - 2026-10-15T094900Z-fix-windows-ci-encoding
  - 2026-10-15T095832Z-promote-candidates-and-utf8-tools
promoted_to: AGENTS.md
---

# 開発ToolとHookの入出力をUTF-8へ固定する

## 観測した反復

Windowsでは、Pythonの標準入出力がConsoleの文字コード（ローカルはcp932、CIランナーはcp1252）に
なる。このため、日本語を含む入出力が同じ日に独立した3回の作業で失敗した。

- Agent Hookの作業では、Git保護HookがUTF-8のHook入力をcp932で読み、日本語のコミット
  メッセージを含む`git commit`を誤って拒否するところだった
- Windows CIの修正では、`tools/check.py`と同期Scriptの日本語出力が`UnicodeEncodeError`で失敗した
- 上記の修正をマージした後も、新しく追加した`tools/preview_output.py`と`tools/hooks/`の2つの
  Scriptが同じ対策を持たず、`tests/test_tool_output_encoding.py`へ追加して初めて検出された

対策がScriptごとの記述に分散しているため、新しいToolを追加するたびに漏れる。

## 昇格案

`AGENTS.md`のコーディング規約へ、次の短い規約を追加する。

- `tools/`の実行Scriptは`main`の最初に標準出力と標準エラーをUTF-8へ再設定し、
  `tests/test_tool_output_encoding.py`へ`--help`などの実行例を追加する
- 外部プロセスとJSONをやり取りするHookは、標準入力をバイト列からUTF-8で読み、
  JSONはASCIIエスケープで出力する

あわせて、再設定処理を`tools/`内の共通Moduleへまとめるか、`tests/test_tool_output_encoding.py`が
`tools/`配下の実行Scriptを自動的に列挙するようにして、追加漏れをTestで防ぐ案を検討する。

## 昇格条件

- 独立した複数セッションの根拠、または利用者の明示的な昇格依頼がある
- 既存の正本やSkillと責務が重複しない
- 入力、手順、期待結果、失敗時の扱いを検証できる
- 秘密情報と個人情報を含まない
