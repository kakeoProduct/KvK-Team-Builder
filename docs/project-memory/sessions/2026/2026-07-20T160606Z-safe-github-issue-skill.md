---
type: session
id: 2026-07-20T160606Z-safe-github-issue-skill
title: 安全なGitHub Issue作成・削除Skillを追加
status: current
created_at: '2026-07-20T16:06:06Z'
base_commit: c2b62044c224fb46167aec144fcd717092ca864a
final_commit: c2b62044c224fb46167aec144fcd717092ca864a
tags:
- github
- security
- skill
related_paths:
- .agents/skills/manage-github-issue/SKILL.md
- .agents/skills/manage-github-issue/agents/openai.yaml
- AGENTS.md
- DEVELOPMENT.md
- docs/adr/0009-safe-github-issue-lifecycle.md
- docs/adr/README.md
- tests/test_ai_harness.py
---

# 安全なGitHub Issue作成・削除Skillを追加

## 利用者の依頼

GitHub Issueの作成と削除を安全に行う共有Skillを追加する

## 実装結果

重複確認付きの単一Issue作成、Pull Request除外と二段階承認付きの単一Issue完全削除を定義し、Repository規約、開発ガイド、ADR、構造テストへ反映した。

## 重要な判断

- Issue作成の明示を1件の作成承認とし、完全削除は対象情報提示後の再承認と直前再検証を必須にした。コメント本文は取得せず、TOKENはCodespaces Secretまたは既存GitHub CLI認証からのみ利用する。

## 検証

- Skill構造検証成功。tests/test_ai_harness.pyは8件成功。python tools/check.pyはRuff、mypy、pytest 33件すべて成功。gh issue listの読み取り確認成功。前方テストでMust指摘なし。

## 未完了事項

- GitHub上の実Issue作成と完全削除は、外部作用および破壊的操作のため実施していない。

## 正本への参照

- `.agents/skills/manage-github-issue/SKILL.md`
- `.agents/skills/manage-github-issue/agents/openai.yaml`
- `AGENTS.md`
- `DEVELOPMENT.md`
- `docs/adr/0009-safe-github-issue-lifecycle.md`
- `docs/adr/README.md`
- `tests/test_ai_harness.py`
