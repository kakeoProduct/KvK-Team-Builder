---
name: choose-skill
description: 利用可能なSkillから依頼に合う作業経路を選び、優先するSkillと理由を案内する。
---

# Skillを選ぶ

利用者の目的を一文で整理し、Repository固有Skillを最優先に選ぶ。推奨するSkill名、選定理由、
必要な前提だけを返す。選択後の作業は、利用者が同時に実行を依頼した場合だけ開始する。

## Repository固有の経路

- 編成人数、VC、集結主、参加時刻、戦力関係、警告、目的関数、入力記法の変更:
  `$change-kvk-rules`
- コード、文書、Pull Request、ブランチ差分のレビュー: `$review-kvk-change`
- Web UIの実装、変更、レビュー: `$apple-design`
- Pull Requestの準備または作成: `$create-github-pr`
- GitHub Issueの準備、作成、完全削除: `$manage-github-issue`
- Repository変更の開始と完了記録: `$maintain-project-memory`
- Skill、Review Agent、Agent Hookの追加・変更・削除: `$change-ai-harness`
- 一次情報で主張を判定し、出典と確認日を付けて報告する（保存は依頼時だけ）: `$research`

## 一般的な開発経路

- 原因が不明な不具合や性能劣化の診断: `$diagnosing-bugs`
- テスト駆動の機能実装またはバグ修正: `$tdd`
- Moduleの境界、Interface、責務の設計: `$codebase-design`
- 用語、Domain Model、ADRの整理: `$domain-modeling`
- 設計上の疑問を動く形で確かめる: `$prototype`
- mergeまたはrebaseの競合を解消する: `$resolving-merge-conflicts`
- Skill、`AGENTS.md`、Agent向け文書を作成または更新する: `$writing-for-agents`
- 現在の作業を新しいCodex Subagentへ渡す: `$codex-handoff`（Codexのみ）
- CodexのGit操作へ安全策を追加する: `$git-guardrails-codex`（Codexのみ）

## 長い作業の経路

- 曖昧な計画を質問で具体化し、判断を文書へ残す: `$grill-with-docs`
- 合意済みの会話を仕様へまとめる: `$to-spec`
- 仕様を依存関係付きの小さな作業へ分割する: `$to-tickets`
- 仕様またはTicketに沿って実装する: `$implement`
- 複数Sessionを要する大規模な判断を整理する: `$wayfinder`

複数候補がある場合は、主となるSkillを一つ選び、代替候補は判断が変わる条件と一緒に示す。
Repositoryの`AGENTS.md`と対象Skillが競合するときは、`AGENTS.md`を優先する。
