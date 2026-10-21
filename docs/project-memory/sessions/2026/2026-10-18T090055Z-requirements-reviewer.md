---
type: session
id: 2026-10-18T090055Z-requirements-reviewer
title: 文書だけの変更もレビューし、要件レビュー担当を追加
status: current
created_at: '2026-10-18T09:00:55Z'
base_commit: b2bcd4ecdaf067efa2228420d7505941264eb33d
final_commit: b2bcd4ecdaf067efa2228420d7505941264eb33d
tags:
- ai-harness
- review
related_paths:
- .agents/skills/review-kvk-change/SKILL.md
- .agents/skills/review-kvk-change/references/review-report-template.md
- .claude/agents/kvk-requirements-reviewer.md
- .claude/skills/review-kvk-change/SKILL.md
- .claude/skills/review-kvk-change/references/review-report-template.md
- .codex/agents/kvk-requirements-reviewer.toml
- .github/pull_request_template.md
- AGENTS.md
- DEVELOPMENT.md
- docs/adr/0024-review-document-changes-and-requirements.md
- docs/adr/README.md
- tests/test_agent_hooks.py
- tests/test_ai_harness.py
---

# 文書だけの変更もレビューし、要件レビュー担当を追加

## 利用者の依頼

文書のみの変更でもAIレビューを回し、要件が正確か・考慮漏れがないかなど要件定義の不足を観点に持たせたい

## 実装結果

読み取り専用のkvk-requirements-reviewer（出典との一致、考慮漏れ、曖昧さ、矛盾、検証可能性、要件ID、秘密情報）を追加。review-kvk-changeで文書だけの変更も対象にし、要件・ADR・README・AGENTSなどの変更で要件レビュー担当を割り当てる。出典はtmp/review-sources/で渡す。テンプレートに出典と運用者への確認事項を追加。AGENTS、DEVELOPMENT、PRテンプレート、ADR 0024、構造テストを更新

## 重要な判断

- 既存のdomain-reviewerへ足さず独立した担当にした（出典照合と運用出力の退行は性質が違い、battle_timingの要件も対象になるため）
- Repository外の出典は実運用の名前を含むため、Git管理外のtmp/review-sources/に置いて渡す

- レビュー指摘（Must 2件、Should 8件）に対応: 4担当を常に割り当て、文書だけの変更も省略しない（誤字・共有記憶だけは理由を書いて見送り可）、create-github-prとimplementの起動条件を更新、tmp/review-sources/を読み取り専用の例外に追加、出典の名前をレビュー結果とPRコメントへ転記しない、秘密情報の定義を参加者一覧由来の情報に限定、ADR 0024で置き換えるADR 0002・0007・0022を明記し未マージのADR 0023への参照を削除、構造テストを規範文の照合と後退の検出へ強化

## 検証

- python tools/check.py: 成功

## 未完了事項

- 新しいレビュー担当はClaude Codeの新しいSessionから使える。それまではフォールバックで主エージェントが要件の観点を確認する

## 正本への参照

- `.agents/skills/review-kvk-change/SKILL.md`
- `.agents/skills/review-kvk-change/references/review-report-template.md`
- `.claude/agents/kvk-requirements-reviewer.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.claude/skills/review-kvk-change/references/review-report-template.md`
- `.codex/agents/kvk-requirements-reviewer.toml`
- `.github/pull_request_template.md`
- `AGENTS.md`
- `DEVELOPMENT.md`
- `docs/adr/0024-review-document-changes-and-requirements.md`
- `docs/adr/README.md`
- `tests/test_agent_hooks.py`
- `tests/test_ai_harness.py`
