# プロジェクト記憶索引

このファイルは`session_memory.py rebuild-index`で生成する。手作業で編集しない。
記憶は来歴と引継ぎの補助であり、README、ADR、設定、テストなどの正本を上書きしない。

## 昇格候補

| 候補 | 状態 | 昇格先 | 根拠数 |
|---|---|---|---:|
| [AIハーネス変更時の整合手順](candidates/ai-harness-change-procedure.md) | promoted | skill | 6 |
| [開発ToolとHookの入出力をUTF-8へ固定する](candidates/windows-utf8-tool-io.md) | promoted | agents-guidance | 3 |

## 変更セッション

| セッション | 状態 | タグ | 関連パス数 |
|---|---|---|---:|
| [CIのトリガー重複を除き、Pull Requestの古い実行を中止する](sessions/2026/2026-10-22T101851Z-ci-dedupe-triggers.md) | current | ci, github-actions | 6 |
| [devとmainに分けるブランチ運用を導入する](sessions/2026/2026-10-21T143919Z-20261021t135229z-f63f9853.md) | current | ai-harness, git-workflow | 11 |
| [公開に備えて実在の名前とゲーム名を伏せる](sessions/2026/2026-10-19T182741Z-d33b819a-e089-4059-8eb6-eb7120561ecb.md) | current | ai-harness, publish | 111 |
| [作成者の仮定の前文から#44のmerge前の記述を外す](sessions/2026/2026-10-19T152314Z-team-building-requirements-adr0024-reference.md) | current | requirements, team-building | 1 |
| [PR #44をmergeしたmainを取り込み、ADRの一覧と共有記憶の索引の競合を解消する](sessions/2026/2026-10-19T151525Z-team-building-requirements-merge-main.md) | current | requirements, team-building | 32 |
| [往復が終わる理由を前提つきで書き、旧Q-092の決定と作成者の分担を分ける](sessions/2026/2026-10-19T150025Z-team-building-requirements-round16.md) | current | requirements, team-building | 3 |
| [回答を受けた実行の性質の語を定義し、検証方法と例を足す](sessions/2026/2026-10-19T144745Z-team-building-requirements-round15.md) | current | requirements, team-building | 5 |
| [回答の確かめ方を満たすべき性質と例にし、手順は実装Issueで決める](sessions/2026/2026-10-19T143232Z-team-building-requirements-round14.md) | current | requirements, team-building | 5 |
| [申告と照らす差分の範囲と、基準ブランチの取り込み方を決める](sessions/2026/2026-10-19T142933Z-review-diff-range-and-merge-import.md) | current | ai-harness, review | 10 |
| [回答を問いの対象の順に確かめ、成り立たない指定は問い直して往復を終える](sessions/2026/2026-10-19T140908Z-team-building-requirements-round13.md) | current | requirements, team-building | 4 |
| [見直しの申告の渡し方と、Pull Request前の仮定の置き場所を決める](sessions/2026/2026-10-19T140529Z-review-declaration-and-assumption-storage.md) | current | ai-harness, review | 12 |
| [24時より前の休止を8人未満に数え、指定の確かめ方を往復で終わる形にする](sessions/2026/2026-10-19T134831Z-team-building-requirements-round12.md) | current | requirements, team-building | 5 |
| [見直しの判定を作成者の申告で決め、ほかのPull Requestの案の読み先を決める](sessions/2026/2026-10-19T134454Z-review-revision-declaration.md) | current | ai-harness, review | 10 |
| [24時より前の8人未満を休止より先に比べ、選択肢の判定を往復しても一つに決める](sessions/2026/2026-10-19T132641Z-team-building-requirements-round11.md) | current | requirements, team-building | 4 |
| [作成者の仮定の記録先を表にし、残った振り返りの案をレビュー結果に残す](sessions/2026/2026-10-19T132544Z-review-assumption-destinations.md) | current | ai-harness, review | 12 |
| [休止を最上位の指標で避け、序盤はリーダー不在でも出撃させる](sessions/2026/2026-10-19T125007Z-team-building-requirements-round10.md) | current | requirements, team-building | 5 |
| [Review Agentは確認事項の基準をSkillから参照し、自己点検リストを育てる](sessions/2026/2026-10-19T124915Z-review-agents-refer-skill.md) | current | ai-harness, review | 21 |
| [休止を6人以下と同じく扱い、分かりやすい配置を優先する](sessions/2026/2026-10-19T112840Z-team-building-requirements-round9.md) | current | requirements, team-building | 6 |
| [振り返りをレビューでは案にとどめ、衝突は確認事項にする](sessions/2026/2026-10-19T112755Z-review-self-check-proposals.md) | current | ai-harness, review | 14 |
| [Hypothesisで必須条件の性質テストを導入する](sessions/2026/2026-10-19T101736Z-5b5d0490-6df9-4fde-8147-20569ad36f83.md) | current | testing | 11 |
| [編成の要件定義書へ8回目の回答を反映し、人数の下限を一覧表にまとめる](sessions/2026/2026-10-19T100808Z-team-building-requirements-round8.md) | current | requirements, team-building | 0 |
| [指摘へ対応するたびに自己改善し、確認事項を絞る](sessions/2026/2026-10-19T100720Z-review-self-improvement.md) | current | ai-harness, review | 0 |
| [編成の要件定義書へ7回目の回答を反映する](sessions/2026/2026-10-19T093915Z-team-building-requirements-round7.md) | current | requirements, team-building | 6 |
| [コミット前のレビューを指紋で照合し、未回答の確認事項を承認不可とする](sessions/2026/2026-10-19T093845Z-review-fingerprint-and-verdict.md) | current | ai-harness, review | 15 |
| [編成の要件定義書へ6回目の回答を反映する](sessions/2026/2026-10-18T140646Z-team-building-requirements-round6.md) | current | requirements, team-building | 0 |
| [見送れる変更を3つにそろえ、Shouldの見送りの節とPR本文への追記を定める](sessions/2026/2026-10-18T140613Z-review-skip-and-acceptance-section.md) | current | ai-harness, review | 0 |
| [編成の要件定義書へ5回目の回答を反映する](sessions/2026/2026-10-18T133525Z-team-building-requirements-round5.md) | current | requirements, team-building | 0 |
| [Shouldの受容をPR本文へ記録し、Mustは見送れないと定める](sessions/2026/2026-10-18T133439Z-rereview-acceptance-in-pr-body.md) | current | ai-harness, review | 0 |
| [編成の要件定義書へ4回目の回答を反映する](sessions/2026/2026-10-18T130407Z-team-building-requirements-round4.md) | current | requirements, team-building | 0 |
| [再レビューの対象、投稿の重複防止、終わり方を定める](sessions/2026/2026-10-18T130250Z-rereview-scope-and-termination.md) | current | ai-harness, review | 13 |
| [レビュー指摘への対応後に再レビューする](sessions/2026/2026-10-18T122545Z-rereview-after-fixes.md) | current | ai-harness, review | 9 |
| [KvKチーム編成の要件定義書をレビュー指摘と回答で改訂（#43）](sessions/2026/2026-10-18T121649Z-team-building-requirements-review.md) | current | docs, requirements, team-building | 10 |
| [文書だけの変更もレビューし、要件レビュー担当を追加](sessions/2026/2026-10-18T090055Z-requirements-reviewer.md) | current | ai-harness, review | 13 |
| [KvKチーム編成の要件定義書を追加（#42）](sessions/2026/2026-10-18T075627Z-team-building-requirements.md) | current | docs, requirements, team-building | 11 |
| [BuildTeamPlanとValidatedTeamPlanを導入（#28後半）](sessions/2026/2026-10-18T060628Z-build-team-plan.md) | current | architecture, ddd, refactoring | 20 |
| [AIレビュー結果のテンプレート保存とPull Requestへの投稿](sessions/2026/2026-10-18T024101Z-review-pr-comment.md) | current | ai-harness, review | 11 |
| [編成処理をkvk_team.team_buildingへ移行（#28 PR1）](sessions/2026/2026-10-18T023411Z-team-building-move.md) | current | architecture, ddd, refactoring | 62 |
| [モノリポジトリの構成と2つのコンテキストをADR 0021で決定](sessions/2026/2026-10-17T141540Z-repository-structure-adr.md) | current | architecture, ddd | 8 |
| [個人所有Projectを扱うGitHub認証方針をADR 0008へ追加](sessions/2026/2026-10-17T133807Z-gh-auth-token-policy.md) | current | ai-harness, github | 8 |
| [web補助ツールの要件定義書を追加](sessions/2026/2026-10-17T123159Z-web-tools-requirements.md) | current | docs, web-tools | 12 |
| [CP-SATテストの決定化と時間切れエラーの区別](sessions/2026/2026-10-17T120208Z-c4acdb54-ffb9-40ba-bdd2-999316684994.md) | current | optimizer, testing | 13 |
| [Claude Codeのプレビュー起動設定をGit管理外にする](sessions/2026/2026-10-17T114420Z-ignore-claude-launch-json.md) | current | dev-environment | 3 |
| [読み取り専用HookをPython起動の少ない形へ絞る](sessions/2026/2026-10-17T093554Z-narrow-read-only-hook.md) | current | agent-hooks, ai-harness | 8 |
| [Review Agentの読み取り専用をPreToolUse Hookで強制](sessions/2026/2026-10-17T091948Z-enforce-read-only-agents.md) | current | agent-hooks, ai-harness | 0 |
| [Claude Code専用Skill設定と調査結果の独立検証](sessions/2026/2026-10-17T082139Z-skill-settings-evidence-review.md) | current | ai-harness | 17 |
| [Dev Containerで作業ツリーの所有者を実行利用者へそろえる](sessions/2026/2026-10-17T080534Z-match-workspace-owner.md) | current | dev-container, git | 7 |
| [並行Sessionのworktree分離と検証可能な完了・調査・レビュー](sessions/2026/2026-10-15T104835Z-parallel-session-worktree-harness.md) | current | agent-hooks, ai-harness | 32 |
| [昇格候補2件の昇格](sessions/2026/2026-10-15T101300Z-promote-harness-and-utf8.md) | current | ai-harness, windows | 11 |
| [ADR 0014の採用と昇格候補の作成](sessions/2026/2026-10-15T095832Z-promote-candidates-and-utf8-tools.md) | current | ai-harness, windows | 6 |
| [Windows CIの日本語出力エラーを修正](sessions/2026/2026-10-15T094900Z-fix-windows-ci-encoding.md) | current | bugfix, ci, windows | 4 |
| [Agent HookとSkill構成の改善](sessions/2026/2026-10-15T094201Z-agent-hooks-and-skill-cleanup.md) | current | agent-hooks, ai-harness | 37 |
| [web/をPython処理の対象外として明文化](sessions/2026/2026-10-15T093034Z-separate-web-tools.md) | current | scope, web | 6 |
| [CodexとClaude Codeの両対応](sessions/2026/2026-10-15T092436Z-support-codex-and-claude-code.md) | current | agents, claude-code, codex | 0 |
| [Claude用SkillをCodex向けへ移行](sessions/2026/2026-08-11T075714Z-localize-codex-skills.md) | current | ai-harness, codex, skill | 17 |
| [Matt Pocockの共有スキルを追加](sessions/2026/2026-08-11T073050Z-install-mattpocock-skills.md) | current | ai-harness, skill | 98 |
| [Dev ContainerのVS Code Server権限を修正](sessions/2026/2026-07-22T144728Z-fix-dev-container-vscode-server-permissions.md) | current | bugfix, development, docker, vscode | 2 |
| [Dev Container間でVS Code拡張機能を共有](sessions/2026/2026-07-22T144313Z-shared-dev-container-extensions.md) | current | codex, development, docker, vscode | 5 |
| [Windowsローカル開発用Dev Containerを追加](sessions/2026/2026-07-22T143359Z-windows-dev-container.md) | current | ai-harness, development, docker, windows | 9 |
| [GitHub Issue Formsを追加](sessions/2026/2026-07-20T162938Z-github-issue-forms.md) | current | github, issue-template, security | 3 |
| [安全なGitHub Issue作成・削除Skillを追加](sessions/2026/2026-07-20T160606Z-safe-github-issue-skill.md) | current | github, security, skill | 7 |
| [Codespaces認証対応のPR作成Skillを追加](sessions/2026/2026-07-20T154028Z-20260720t153401z-ea877630.md) | current | ai-harness, github, security, skill | 8 |
| [レビュー指摘を人間向け3段階へ変更](sessions/2026/2026-07-20T134853Z-review-decision-levels.md) | current | ai-harness, review, skill | 8 |
| [変更Sessionの共有記憶と知識昇格を実装](sessions/2026/2026-07-20T133550Z-project-memory-and-promotion.md) | current | ai-harness, memory, skill | 12 |
