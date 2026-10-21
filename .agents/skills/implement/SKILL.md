---
name: implement
description: 合意済みの仕様、Ticket、または依頼を、このRepositoryの完了条件まで実装する。複数Sessionにまたがる作業は進捗ファイルで中断と再開を管理する。
---

# 合意済みの作業を実装する

仕様やTicketを根拠に実装し、`AGENTS.md`の完了条件をすべて満たしてから報告する。途中で
止まっても、次のSessionが同じ地点から再開できる状態を保つ。

## 開始する

1. `$maintain-project-memory`の手順で開始状態を保存する。Claude CodeでHookが保存済みと
   Contextに示されている場合は、そのsession_idを使い、startを再実行しない。
2. `start`の出力で`use_separate_worktree`が`true`、またはHookのContextが別Sessionの使用中を
   示す場合は、編集前に下の「Session用worktreeへ移る」に従う。`false`なら現在の作業ツリーで
   進める。
3. 指摘へ対応する作業では、ほかの指摘より先に、前回のレビュー結果の振り返りにある項目の案を、
   `$review-kvk-change`の自己点検リスト（`references/self-check.md`）へ反映して同期する
   （`$review-kvk-change`の「振り返る」）。自己点検リストがないブランチで繰り返しが続いている
   Pull Requestがあれば、その最新のレビュー結果の案も反映する。案の文が該当する行の「確かめること」にすでにあるかで反映済みの案を
   確かめ、同じ案を二重に足さない。基準ブランチに自己点検リストがあり、このbranchにまだなければ、利用者の明示を得て基準ブランチをmergeで
   取り込んでから反映する。
4. `tmp/progress/`に同じ作業の進捗ファイルがあれば読み、「次の一手」から再開する。
   ない場合は、複数Sessionまたは長い作業になりそうなときだけ作成する。
5. `AGENTS.md`の変更手順に従い、関連するREADME、Architecture、設定、テストを読む。
6. 編成ルールの変更を含む場合は`$change-kvk-rules`を併用する。
7. 仕様と正本が衝突する場合や、依頼範囲が曖昧な場合は、推測で進めず利用者へ確認する。
8. 利用者から受け取ったルール文書や決定事項など、Repositoryにない出典は、受け取った時点で
   Git管理外の`tmp/review-sources/`へ保存し、レビューで絶対パスを渡せるようにする。

## Session用worktreeへ移る

同じ作業ツリーで別Sessionが編集すると、差分、品質ゲート、共有記憶の判定が混ざる。別Sessionが
使用中のときだけ、Session専用のworktreeとbranchで作業する。使用中でなければ作らない。

1. 現在の作業ツリーの開始状態を`discard --session-id <session_id>`で破棄する。別Sessionの差分を
   自分の記憶として記録しないため、`finish`は使わない。
2. 現在のHEADから作る。branch名、worktree名、コミットメッセージには、`AGENTS.md`の伏せる語の規則
   （ADR 0026）に当たる語を使わない。Claude Codeでは`CLAUDE.md`の読み替えに従う。それ以外では
   次を実行し、以後の作業Directoryを移す。

   ```text
   git worktree add -b <branch名> .worktrees/<作業の短い英語名> HEAD
   ```

3. 移動先で`git status --short`と`git log -1 --oneline`を確認し、元と同じコミットから始まる
   ことを確かめる。元の作業ツリーにある未コミットの変更は引き継がれない。必要なら利用者へ確認する。
4. 移動先で`$maintain-project-memory`の`start`を実行する。Claude Codeでは同じsession_idを渡す。
5. 以後の編集、テスト、`python tools/check.py`、`finish`はすべて移動先で行う。

完了後もworktreeとbranchは残し、パスとbranch名を報告する。コミット、統合、`git worktree remove`は
利用者が明示した場合だけ行う。未コミットの変更を失う`git worktree remove --force`は使わない。

## 完了条件を先に決める

実装前に、次を含む完了条件を進捗ファイルまたは作業メモへ書く。各条件は、実行したコマンドと
結果を会話に表示すれば第三者が達成を判定できる形で書く。

- 依頼された振る舞いを示すテストが成功する
- `python tools/check.py`が成功する
- 編成または表示を変えた場合、`python tools/preview_output.py`の自己チェックと警告を確認した
- 利用者向け契約、Architecture、ADRが実装と一致している
- 共有記憶を`finish`で記録した

完了条件には、進められなくなったときの停止条件も含める。たとえば、正本の衝突、利用者だけが
持つ情報や権限の不足、同じ失敗の反復では、推測で続けず止まって障害を報告する。

## 実装する

- `$tdd`で、合意済みの境界ごとに失敗するテストから進める。
- 変更中は対象のテストファイルを実行し、完了前に`python tools/check.py`を1回実行する。
- テストを削除、スキップ、弱体化して品質ゲートを通さない。
- 区切りごとに進捗ファイルを更新する。

## 進捗ファイル

`tmp/progress/<作業の短い英語名>.md`はGit管理外のローカルファイルとする。秘密情報や会話全文を
書かず、次の見出しだけを短く保つ。

```markdown
# 作業名

## 目的
## 完了条件
## 完了済み
## 次の一手
## 判断と根拠
## 検証結果
```

## 仕上げる

1. 完了条件を1つずつ確認し、検証コマンドと結果を会話に表示する。未達があれば報告に明記する。
2. 差分があれば、文書だけの変更でも`$review-kvk-change`を使用する（ADR 0024）。意味を変えない誤字の修正だけの変更、共有記憶（`docs/project-memory/`）だけの変更、意味を変えない誤字の修正とそのセッションの共有記憶の記録だけを含む変更は、
   理由を報告すれば見送れる。指摘へ対応した場合は、`$review-kvk-change`の自己点検リスト
   （`references/self-check.md`）を確かめ、「確かめること」を変えた分類を申告してから、対応後の差分を
   もう一度レビューし（再レビュー）、`$review-kvk-change`の終わる条件を満たすまで繰り返す。`Must`は
   見送れない。見送った`Should`は、`$review-kvk-change`の手順7に従ってレビュー結果の「見送り」の節に
   記録する。レビューの印には、基準からの変更の指紋（`diff`）を書く。
3. `$maintain-project-memory`の`finish`で共有記憶を記録する。出力に`promotion_hints`が
   あれば、昇格候補の作成を利用者へ提案する。自動では作成しない。
4. 完了した作業の進捗ファイルは削除する。
5. コミット、push、Pull Request作成は、利用者が明示した場合だけ行う。コミットとpushの前に、
   コミットメッセージとbranch名が`AGENTS.md`の伏せる語の規則（ADR 0026）に当たらないことを確かめる。Pull Requestがある状態で
   pushしたら、まだ投稿していない`$review-kvk-change`の結果を、その手順3の確認を行ってから投稿する
   （ADR 0024）。
