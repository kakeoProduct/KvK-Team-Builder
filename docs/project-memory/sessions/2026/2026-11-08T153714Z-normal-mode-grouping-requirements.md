---
type: session
id: 2026-11-08T153714Z-normal-mode-grouping-requirements
title: 通常モードのグループの要件を要件定義書へ反映
status: current
created_at: '2026-11-08T15:37:14Z'
base_commit: 3c927ae18802416a014d56d278b8c1123388d226
final_commit: 3c927ae18802416a014d56d278b8c1123388d226
tags:
- requirements
- review
related_paths:
- .agents/skills/review-kvk-change/references/self-check.md
- .claude/skills/review-kvk-change/references/self-check.md
- docs/requirements/team-building/README.md
- docs/requirements/team-building/data-formats.md
- docs/requirements/team-building/formation-rules.md
- docs/requirements/team-building/open-questions.md
- docs/requirements/team-building/output-and-screen.md
---

# 通常モードのグループの要件を要件定義書へ反映

## 利用者の依頼

引き継ぎ資料をもとに、通常モードのグループ（応援をグループ内に限る再編成の案、グループ別の人数と治療時間の目安、同盟の移動人数、時間未定の移動先、同じグループにしたい組）を要件定義書へ反映する

## 実装結果

FRM-004、FRM-037、FRM-042、FRM-047、FRM-073、11章の前文、OUT-004、OUT-005、OUT-007、UI-013、DAT-007、DAT-008、用語、分割案を直し、FRM-077、FRM-110〜FRM-112、12章、OUT-019を加えた。決定を旧Q-130〜旧Q-144、作成者の仮定をA-30〜A-36に記録した。再レビューで3回以上続いたC2とC14の見直し案を自己点検リストへ反映した

## 重要な判断

- 通常モードと総力モードのグループを1つの概念にまとめ、総力の規則と同盟移動の必須条件は総力モードだけに当てはめる（旧Q-139）
- 同じグループにしたい組の指標はFRM-037の⑥の直後に置く（旧Q-135）。待機と時間未定の移動先は個別の指定、別枠リーダーは自分の隊のグループ、既定の移動先、今の同盟の順（旧Q-140〜旧Q-143、A-36（作成者の仮定））
- （作成者の仮定）A-30〜A-36: グループの指定と隊数を減らした場合、組の数え方と保持、治療時間の書き方、ファイルの節と注記の順、再編成の案（上位3件、0件、時間切れ、選んだ案は回答）、応援をグループ内に限る区分と選び直し、既定の移動先の順。目的関数と表示を変える仮定のため、Pull Request本文の「判断と影響」に載せる
- 見送り（利用者が2026-11-08に選択）: 選び直しの判定で比べる「前回」と「問いの対象」の範囲（A-35）は実装Issueの2と5で決める。詳細はtmp/reviews/worktree-normal-mode-grouping.mdの「見送り」の節

## 検証

- python tools/check.py が成功（各修正の後に実行）
- $review-kvk-change: 初回と7回の再レビュー。Mustは初回の1件を解消し、最後の結果はShould 2件を見送り

## 未完了事項

- コミット、push、Pull Requestの作成は未実施（利用者の明示を待つ）
- このworktreeにtools/review_query.pyがなく、レビュー担当がBashを使えなかった（Hookはメインの作業ツリーの設定から読まれる）

## 正本への参照

- `.agents/skills/review-kvk-change/references/self-check.md`
- `.claude/skills/review-kvk-change/references/self-check.md`
- `docs/requirements/team-building/README.md`
- `docs/requirements/team-building/data-formats.md`
- `docs/requirements/team-building/formation-rules.md`
- `docs/requirements/team-building/open-questions.md`
- `docs/requirements/team-building/output-and-screen.md`
