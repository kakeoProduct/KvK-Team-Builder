---
type: session
id: 2026-07-20T162938Z-github-issue-forms
title: GitHub Issue Formsを追加
status: current
created_at: '2026-07-20T16:29:38Z'
base_commit: c2b62044c224fb46167aec144fcd717092ca864a
final_commit: c2b62044c224fb46167aec144fcd717092ca864a
tags:
- github
- issue-template
- security
related_paths:
- .github/ISSUE_TEMPLATE/bug_report.yml
- .github/ISSUE_TEMPLATE/feature_request.yml
- tests/test_ai_harness.py
---

# GitHub Issue Formsを追加

## 利用者の依頼

Issue投稿用のTemplateをRepositoryへ追加する

## 実装結果

不具合報告と機能要望のGitHub Issue Formsを日本語で追加し、重複確認、秘密情報確認、再現情報、受け入れ条件を構造テストで固定した。

## 重要な判断

- 既存labelやassigneeを推測せず、空欄Issueを禁止するconfig.ymlも追加しない。公式Schemaに沿ったYAML Formsだけを提供する。

## 検証

- python -m pytest tests/test_ai_harness.py -qは9件成功。python tools/check.pyはRuff、mypy、pytest 34件すべて成功。git diff --checkも成功。

## 未完了事項

- GitHub上のTemplate選択画面はdefault branchへ反映後に確認する。

## 正本への参照

- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `tests/test_ai_harness.py`
