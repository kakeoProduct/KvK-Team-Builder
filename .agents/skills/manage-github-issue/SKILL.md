---
name: manage-github-issue
description: GitHub Issueの題名と本文をRepositoryの文脈から作成し、重複を確認してGitHub CLIで公開する。または、指定された単一IssueをPull Requestではないと検証し、利用者の再承認後に完全削除する。Issueの作成、本文の準備、または削除を依頼された場合に使用し、Pull Request操作、Issueの編集・コメント・一括操作だけの依頼には使用しない。
---

# GitHub Issueを作成または削除する

認証済みのGitHub CLIを使い、Issueの作成と単一Issueの完全削除を安全に扱う。削除は取り消せない
ため、最初の依頼だけでは実行せず、対象を再取得して提示した後の再承認を必須とする。

## 操作と外部作用の範囲を確定する

1. `AGENTS.md`を最後まで読み、`DEVELOPMENT.md`と`.github/ISSUE_TEMPLATE/`が存在すれば関連する
   Templateを読む。
2. 「本文を作る」「準備する」「プレビューする」という依頼では、GitHub上にIssueを作成しない。
   「Issueを作成する」という明示的な依頼を、単一の`gh issue create`の承認として扱う。
3. 削除依頼では、対象の再取得とPull Request除外を行い、Repository、番号、題名、状態、URL、
   コメント数、完全削除で復元できないことを提示する。その提示後に、利用者が同じ対象の削除を
   再承認した場合だけ`gh issue delete`を実行する。最初の削除依頼を再承認として扱わない。
4. 解決済み、重複、古いIssueには通常はCloseを勧めるが、削除をCloseへ暗黙に置き換えない。
   Issueの編集、Close、再Open、コメント、移送、Pin、Pull Request操作、一括操作を、このSkillの
   暗黙の権限に含めない。
5. 番号の範囲、glob、検索結果全件など複数対象の削除を受け付けない。1回の実行で作成または削除
   するIssueは1件に限定する。

## 認証を安全に確認する

1. CodespacesではCodespaces Secretの`GH_TOKEN`、その他の環境では既存のGitHub CLI認証を
   利用する。`.env`、Repository、Skill、Git設定へTOKENを保存しない。認証方式とスコープの上限は
   ADR 0008に従う。個人所有のProjectはfine-grained PATでは読めないため、Projectを扱う場合は
   `gh auth login --web`のOAuthトークンまたはclassic PATが必要になる。
2. `gh auth status --active --hostname github.com`で認証を確認する。出力の`Token scopes`に
   ADR 0008の上限を超えるスコープがあれば、外部作用の前に利用者へ報告する。失敗時は
   `gh api user --jq .login`を読み取り専用で実行し、接続制限と`401`認証失敗を区別する。
   sandboxのNetwork制限で失敗した場合は、同じ読み取り専用検査の承認を得て再実行する。
3. `gh auth token`、`gh auth status --show-token`、環境変数の値の表示、`~/.config/gh/hosts.yml`の
   読み取りを行わない。利用者へTOKENを
   会話、File、Command引数へ貼り付けるよう求めない。
4. 認証、対象Repository、または必要な権限を確認できない場合は、外部作用を行わず停止する。

## Issueを作成する

1. `git remote -v`または利用者指定から対象Repositoryを確定する。Issueが実装候補に関係する場合は、
   関連するREADME、設計文書、テスト、既存Issue Templateを読み、事実と期待結果を整理する。
2. 題名の主要語で
   `gh issue list --repo <owner/repo> --state all --search <query> --json number,title,state,url`
   を実行する。同一または実質的に同じIssueがあれば新規作成せず、そのURLと差異を報告する。
   本文の準備だけでも読み取り専用検索は実行できるが、「GitHubへ接続しない」という依頼があれば
   省略し、重複未確認であることを本文案と報告に明記する。
3. 題名と本文には、`AGENTS.md`の伏せる語の規則（ADR 0026）に当たる語を書かない。
   RepositoryのIssue Templateがあれば見出しと指示を正本にする。Templateがなければ、該当する
   項目だけを使って本文を構成する。
   - 背景と目的
   - 期待する結果または受け入れ条件
   - Bugなら再現手順、期待する動作、実際の動作、環境
   - 関連する文書、Issue、Pull Request、制約
4. 事実と推測を区別し、不明点を捏造しない。label、assignee、milestone、Project、Issue typeは、
   利用者指定またはRepositoryの明文化された規約がある場合だけ指定する。
   このRepositoryでは次を規約とする。
   - 機能単位の開発の親Issueは最上位に置き、Project「KvK Utility Tool」の`Hierarchy`を`Epic`と
     する。機能Epicどうしを親子にしない
   - 画面、基盤、設計などの子Issueは、GitHubのSub-issueで親へ結び、`Hierarchy`を`Child`とする
   - 作成後は親側のSub-issue一覧とProjectの`Hierarchy`を再取得し、両方がそろっていることを
     確認する。Projectを読めない認証では、未確認であることを報告する
5. TOKEN、個人情報、非公開URL、長いLogなどの秘密情報を題名や本文へ含めない。本文をOSの一時
   Fileへ安全に書き、shell引数へ展開せず`--body-file`で渡す。
6. 作成前にRepository、題名、本文、重複確認結果、指定されたmetadataを要約する。作成が明示
   されていれば、結果を変える曖昧さがない限り再確認のためだけに停止しない。
7. `gh issue create --repo <owner/repo> --title <title> --body-file <path>`を非対話で実行する。
   作成後は返された番号を使い、`gh issue view <number> --repo <owner/repo> --json number,title,state,url`
   で結果を再取得する。URLと作成内容を報告し、一時Fileを破棄する。
8. 作成結果が不明な失敗では自動的に再作成しない。重複検索を再実行し、作成済みでないことを
   確認してから原因と安全な次の操作を報告する。

## 単一Issueを完全削除する

1. 利用者から対象Repositoryと単一のIssue番号またはURLを得る。対象を推測せず、Repository、番号、
   題名のいずれかが食い違う場合は停止する。
2. `gh issue view <number-or-url> --repo <owner/repo> --json number,title,state,url,author`で最新状態を
   取得する。続けて`gh api repos/<owner>/<repo>/issues/<number>`を読み取り専用で実行し、REST応答の
   `comments`数値をコメント数として使い、`pull_request`が存在しないことを確認する。GitHub APIでは
   Pull RequestもIssueとして返るため、`pull_request`が存在する対象は削除せず、このSkillの対象外
   として報告する。コメント本文は取得しない。
3. Repository、番号、題名、状態、URL、コメント数と「完全削除は取り消せず復元できない」ことを
   利用者へ提示する。この提示後に、同じ番号またはURLを明示した削除の再承認を待つ。
4. 再承認が別の対象を示す、曖昧である、または対象が提示後に変わった場合は、手順1から再検証する。
   Repository管理者権限を確認できない場合も削除しない。
5. 再承認の直後に手順2の読み取りを再実行し、Repository、番号、題名、URLが提示時と一致し、
   `pull_request`が存在しないことを再確認する。不一致または取得失敗なら削除せず、手順3へ戻る。
6. 再検証後だけ`gh issue delete <number> --repo <owner/repo> --yes`を実行する。`--yes`はGitHub CLIの
   対話Promptを省略するためのもので、利用者の再承認を省略する根拠にはしない。
7. 削除後はREST APIで同じ対象を読み取り、認証済みの読み取りに対する`410 Gone`または削除済みで
   参照不能な応答を確認する。削除Commandの結果が不明でも自動再試行せず、状態と失敗理由を報告する。
8. 削除したRepository、番号、題名、検証結果を報告する。削除前の本文やコメントを別の場所へ保存
   せず、秘密情報を出力へ複製しない。
