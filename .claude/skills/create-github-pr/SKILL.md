---
name: create-github-pr
description: 現在のGitブランチと基準ブランチとの差分、Pull Requestテンプレート、検証結果を根拠に、GitHub Pull Requestのタイトルと本文を作成し、GitHub CLIで重複なく公開する。PR本文の準備、Draft PR、またはReady PRの作成を依頼された場合に使用し、レビューだけ、Issue操作、修正実装だけの依頼には使用しない。
---

<!-- このファイルは tools/sync_agent_config.py が.agents/skills/create-github-pr/SKILL.mdから生成します。直接編集せず、正本を変更してから同期してください。 -->

# GitHub Pull Requestを作成する

既存の開発契約と実行した検査を根拠に、再現可能なPull Requestを作成する。TOKENを管理せず、
認証済みのGitHub CLIだけを利用する。

## 外部作用の範囲を確定する

1. `AGENTS.md`を最後まで読み、`DEVELOPMENT.md`と`.github/pull_request_template.md`の関連箇所を
   読む。
2. 「本文を作る」「準備する」「プレビューする」という依頼では、pushとPull Request作成を
   行わない。「Pull Requestを作成する」という明示的な依頼を、現在ブランチの通常pushと
   `gh pr create`の承認として扱う。Codexでは「Pull Requestの対象を検証する」の手順6のとおり、
   pushは利用者に頼む。
3. DraftまたはReadyの指定を尊重する。指定がなく品質ゲートが成功した場合はReadyとし、
   失敗または未実行の場合はReadyを作らない。Draft作成は明示的な依頼がある場合だけ行う。
4. commit、修正実装、Issue操作、force push、既存Pull Requestの更新、mergeを、このスキルの
   暗黙の権限に含めない。

## 認証を安全に確認する

1. CodespacesではCodespaces Secretの`GH_TOKEN`、その他の環境では既存のGitHub CLI認証を
   利用する。`.env`、リポジトリ、Skill、Git設定へTOKENを保存しない。認証方式とスコープの上限は
   ADR 0008に従う。
2. `gh auth status --active --hostname github.com`で認証を確認する。出力の`Token scopes`に
   ADR 0008の上限を超えるスコープがあれば、外部作用の前に利用者へ報告する。失敗時は
   `gh api user --jq .login`を読み取り専用で実行し、接続制限と`401`認証失敗を区別する。
   sandboxのネットワーク制限で失敗した場合は、同じ読み取り専用検査の承認を得て再実行する。
3. `gh auth token`、`gh auth status --show-token`、環境変数の値の表示、`~/.config/gh/hosts.yml`の
   読み取りを行わない。利用者へTOKENを
   会話、ファイル、コマンド引数へ貼り付けるよう求めない。
4. 認証またはRepository権限を確認できない場合は、外部作用を行わず停止する。

## Pull Requestの対象を検証する

1. `git status --short --branch`、`git branch --show-current`、`git remote -v`を確認する。
2. baseを決める（`AGENTS.md`のブランチ運用、ADR 0027）。利用者指定のbaseを優先するが、`dev`以外の
   branchから`main`へのPull Requestと、`main`をheadにしたPull Requestは、利用者が指定しても作らず、
   理由を報告する。baseを省略した場合、作業branchでは`dev`、`dev`では`main`とする。
   `git fetch origin <base>`が失敗する場合（`origin`にbaseがない場合を含む）、detached HEAD、
   base branch上、未コミット変更あり、baseとの差分なしの場合は作成を止める。
3. 手元のbranchは古いことがあるため、`origin/<base>`と比べる。コミット一覧は`origin/<base>..HEAD`、
   差分は`origin/<base>...HEAD`で収集し（`git diff --stat`、`git diff --name-status`）、`main`にだけある
   過去のリリースのmerge commitを一覧へ混ぜない。作業ツリーの未コミット差分を本文へ混ぜない。
   headが`dev`の場合（リリースPull Request）は、`git fetch origin dev`の後、`HEAD`と`origin/dev`が
   同じコミットであることを確かめ、違えば止める。手元の`dev`が遅れているだけなら
   `git merge --ff-only origin/dev`でそろえてよいか利用者へ確認し、進んでいれば`dev`への直接コミット
   として報告する。
4. `gh pr list --state open --head <branch> --json number,title,url`で既存のopen Pull Requestを
   検索する。存在する場合は新規作成せずURLを返す。更新は利用者が明示的に依頼した場合だけ
   別操作として行う。
5. pushの前に、branch名と`origin/<base>..HEAD`のコミットメッセージが`AGENTS.md`の伏せる語の規則
   （ADR 0026）に当たらないことを確かめる。コミットの内容が規則に当たらないよう、HEADで
   `python -m pytest tests/test_repository_scope.py tests/test_team_master_repository.py -k "hidden_words or placeholder"`
   が成功していることも確かめる（伏せる語の検査と、同梱のチームマスタが例のままである検査）。
   一度pushすると消せないため、当たる場合や伏せる語の検査が失敗した場合は、Draftでもpushせず、
   利用者へbranch名の変更やコミットの修正を提案する。品質ゲート全体（`python tools/check.py`）の成功は、
   従来どおりReadyの条件とする。この検査はHEADの内容だけを見る。途中のコミットで加えて後で消した語も
   pushで公開されるため、`origin/<base>..HEAD`の各コミットの差分を目で確かめる（機械の検査はADR 0026の
   見送り）。すでにpushしたbranchやコミットが当たる場合は、Pull Requestを作らずに利用者へ報告する。
6. upstreamが`origin/<branch>`でなければ、upstreamがないものとして扱う（`origin/dev`から作った
   branchが`origin/dev`を追跡している場合を含む）。upstreamがなければ、Pull Request作成が明示されている
   場合だけ現在branchを
   `git push --set-upstream origin <branch>`でpushする。baseや別branchをpushせず、
   `--force`と`--force-with-lease`を使用しない。headが`dev`の場合はpushせず、手順3で確かめた
   `origin/dev`をそのまま使う。CodexではGit保護Hook（`.codex/hooks.json`）が通常のpushも拒否するため、
   pushせずに同じコマンドを利用者に示して実行を頼む。利用者が終えたと答えたら、`git ls-remote --heads origin <branch>`
   のSHAがHEADと一致することを確かめてから次へ進む（ADR 0030）。

## タイトルと本文を作る

1. 1つの利用者価値または技術的目的へ要約する。適切なcommit件名が1つなら再利用し、複数なら
   `type(scope): 日本語の要約`を基本に新しいタイトルを作る。
2. `.github/pull_request_template.md`を毎回正本として読み、見出しとチェック項目を削除しない。
   タイトルと本文には、`AGENTS.md`の伏せる語の規則（ADR 0026）に当たる語を書かない。
3. 本文へ次を簡潔に記載する。
   - 背景と目的、主な変更、利用者または開発者への変化
   - 必須条件、警告、目的関数などの分類、アーキテクチャ、互換性、既知のリスク
   - ADRの参照、またはADR不要の理由
   - 実行した検査の正確なコマンドと結果、未実行項目と理由
   - 生成Markdown、UI、移行手順など、変更に該当する確認資料。確認資料は`AGENTS.md`の伏せる語の規則
     （ADR 0026）に従って作る
   - 保存したレビュー結果の「見送り」の節に記録があれば（「なし」でなければ）、その行（番号、題名、
     場所、レビューした版、受容したリスク、受容した日、状態）を「判断と影響」へ写す
   - 作成者の仮定のうち、Pull Request本文に載せるもの（`$review-kvk-change`の「結果を報告する」の表とその後の
     段落）を、このbranchの共有記憶のセッション記録の「重要な判断」にある「（作成者の仮定）」と、記録先から
     集めて「判断と影響」へ一覧で書く。セッション記録は基準ブランチからの差分で加わったものに限り、後で
     覆して記録先から消えた仮定は写さない
4. checkboxは根拠がある項目だけ`[x]`にする。対象外の項目は理由を添え、未確認を完了として
   扱わない。
5. Issue番号、`Closes`、reviewer、assignee、label、milestone、Projectを推測しない。利用者指定か
   Repositoryの明文化された規約がある場合だけ含める。
6. PR本文をOSの一時ファイルへ安全に書き、`--body-file`で渡す。本文をshell引数へ直接展開せず、
   TOKENや長い検査ログを含めない。

## 検証して作成する

1. 完了前に`python tools/check.py`を実行する。差分があれば、文書だけの変更でも
   `$review-kvk-change`の結果を確認する（ADR 0024）。意味を変えない誤字の修正だけの変更、共有記憶（`docs/project-memory/`）だけの変更、意味を変えない誤字の修正とそのセッションの共有記憶の記録だけを含む変更のどれかで
   レビューを見送った場合は、本文へ理由を記載する。それ以外で未実施ならReadyにしない。
   保存したレビュー結果の印の`head`と`diff`が、HEADと同じ版を指すことを確かめる。
   `python tools/review_fingerprint.py --base <head> --target HEAD`の出力が`diff`と一致することを
   条件とする。満たさなければ再レビューを求め、Readyにしない。
   レビューの指摘へ対応した場合は、対応後の再レビューの結果も確認する。
2. 作成前にbase、head、Draft状態、タイトル、本文、未解決の警告を要約する。明示済みの作成依頼を
   再確認のためだけに止めないが、曖昧さが外部結果を変える場合は利用者へ確認する。
3. `gh pr create --base <base> --head <branch> --title <title> --body-file <path>`を非対話で実行し、
   Draft指定時だけ`--draft`を加える。`--web`、`--fill`、暗黙のfork作成を使用しない。
4. 作成後に`gh pr view --json url,title,state,isDraft,baseRefName,headRefName`で結果を再取得する。
   URL、base、head、Draft状態、実行した検査と未実行の検査を報告する。
5. 一時本文を破棄する。作成に失敗した場合は再試行で重複しないよう、既存Pull Requestを再検索して
   から原因と安全な次の操作を報告する。
6. 作成に成功し、`$review-kvk-change`の結果が`tmp/reviews/<branch名の/を-に置き換えた名前>.md`に
   保存されていれば、`$review-kvk-change`の「結果を保存してPull Requestへ投稿する」の手順3と同じ確認
   （印の`head`と`diff`がPull Requestのheadと同じ版を指すこと、同じ印の投稿がないこと）を行ってから、
   `gh pr comment <番号> --body-file <そのファイル>`で投稿し、コメントのURLを報告する。同じ版を指さない
   場合は投稿せず、再レビューを求める。保存ファイルがなければ投稿しない（ADR 0022、ADR 0024）。
