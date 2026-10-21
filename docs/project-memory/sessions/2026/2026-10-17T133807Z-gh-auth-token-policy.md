---
type: session
id: 2026-10-17T133807Z-gh-auth-token-policy
title: 個人所有Projectを扱うGitHub認証方針をADR 0008へ追加
status: current
created_at: '2026-10-17T13:38:07Z'
base_commit: 4e266559c9ca494f18c7165c2a63501bec5129fd
final_commit: 4e266559c9ca494f18c7165c2a63501bec5129fd
tags:
- ai-harness
- github
related_paths:
- .agents/skills/create-github-pr/SKILL.md
- .agents/skills/manage-github-issue/SKILL.md
- .claude/skills/create-github-pr/SKILL.md
- .claude/skills/manage-github-issue/SKILL.md
- AGENTS.md
- DEVELOPMENT.md
- docs/adr/0008-codespaces-github-pr-authentication.md
- tests/test_ai_harness.py
---

# 個人所有Projectを扱うGitHub認証方針をADR 0008へ追加

## 利用者の依頼

ADR 0008を修正し、classic PATまたはOAuthトークンを許可してスコープ上限と有効期限を定め、AGENTS.mdと2つのSkillもそろえる

## 実装結果

ADR 0008へ個人所有Project用の認証方式（gh auth login --webのOAuthトークンまたはclassic PAT）、スコープ上限、有効期限、hosts.ymlを読まない規則を追記。AGENTS.md、DEVELOPMENT.md、create-github-pr、manage-github-issue（Hierarchy=Epic/Childの規約を含む）を更新し、構造テストを追加

## 重要な判断

- fine-grained PATは個人所有Projectにアクセスできないため、Project操作時だけ広いTOKENを許可し、スコープをrepo、project、read:org、workflow（ghが加えるgistは許容）に限定する
- 機能単位の親IssueはHierarchy=Epicで最上位、子はSub-issueとHierarchy=Childで結ぶという利用者の規約をmanage-github-issueへ明文化した

## 検証

- python tools/check.py: 成功（89 passed）

## 未完了事項

- 未完了なし

## 正本への参照

- `.agents/skills/create-github-pr/SKILL.md`
- `.agents/skills/manage-github-issue/SKILL.md`
- `.claude/skills/create-github-pr/SKILL.md`
- `.claude/skills/manage-github-issue/SKILL.md`
- `AGENTS.md`
- `DEVELOPMENT.md`
- `docs/adr/0008-codespaces-github-pr-authentication.md`
- `tests/test_ai_harness.py`
