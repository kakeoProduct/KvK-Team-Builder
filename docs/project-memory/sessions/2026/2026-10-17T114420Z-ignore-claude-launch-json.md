---
type: session
id: 2026-10-17T114420Z-ignore-claude-launch-json
title: Claude Codeのプレビュー起動設定をGit管理外にする
status: current
created_at: '2026-10-17T11:44:20Z'
base_commit: 8563eee9739aea5f3cebec383890a795612fac82
final_commit: 8563eee9739aea5f3cebec383890a795612fac82
tags:
- dev-environment
related_paths:
- .claude/launch.json
- .gitignore
- DEVELOPMENT.md
---

# Claude Codeのプレビュー起動設定をGit管理外にする

## 利用者の依頼

.claude/launch.jsonをgitignoreする

## 実装結果

.gitignoreへ.claude/launch.jsonを追加し、DEVELOPMENT.mdの利用者ローカル設定の説明へ加えた

## 重要な判断

- launch.jsonはweb/をローカルで配信するための利用者ごとのプレビュー設定で、どの機能の変更にも含まれないため、settings.local.jsonと同じ扱いにした

## 検証

- git check-ignore -v .claude/launch.json: .gitignore:227で除外
- python tools/check.py: 成功

## 未完了事項

- 未完了なし

## 正本への参照

- `.claude/launch.json`
- `.gitignore`
- `DEVELOPMENT.md`
