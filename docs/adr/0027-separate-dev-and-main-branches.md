# ADR 0027: 統合用の`dev`とリリース用の`main`にbranchを分ける

- 状態: 提案中
- 日付: 2026-10-21

## 背景

これまでのRepositoryは`main`だけを持ち、作業branchのPull Requestは既定branchの`main`へ直接
取り込んでいた。`$create-github-pr`もbaseを省略すると既定branchを使う。

この運用では、取り込んだ直後の変更がそのまま利用者の使う版になる。複数の作業branchを
まとめて確かめてから利用者へ出す段階がなく、統合中の変更とリリース済みの版を区別できない。
利用者は、統合用の`dev`とリリース用の`main`に分ける一般的な運用を求めた。緊急の修正も`dev`を
経由すること、リリースは`dev`から`main`へのPull Requestをmerge commitで取り込むこと、Agentが
`main`から`dev`を作ってpushし、既定branchと保護設定は利用者が行うことも、利用者が決めた。

## 判断

- `main`はリリース済みの版、`dev`は次のリリースへ向けた統合branchとする。利用者が運用に使うのは
  `main`とし、READMEで案内する
- 作業branchは`dev`から作り、`dev`へのPull Requestで取り込む。手元の`dev`は古いことがあるため、
  `git fetch origin dev`の後に`origin/dev`から作る。`--no-track`を付け、作業branchのupstreamが
  `origin/dev`にならないようにする。`origin/dev`へ移った後は、共有記憶の開始状態を取り直す
- `main`へ取り込むのは`dev`からのPull Request（リリースPull Request）だけとし、merge commitで
  取り込む。squashやrebaseで取り込まない。これにより`dev`のコミットをすべて`main`の祖先に含め、
  `main`にはリリースのmerge commitだけが加わる
- 緊急の修正も`dev`を経由する。急ぐ場合は修正を`dev`へ取り込んだ直後にリリースPull Requestを作る
- `main`と`dev`へ直接コミットまたはpushしない。導入時に`main`から`dev`を作る最初の通常pushだけを
  例外とする
- `$create-github-pr`はbaseを省略した場合、作業branchでは`dev`、`dev`では`main`とする。コミット一覧は
  `origin/<base>..HEAD`、差分は`origin/<base>...HEAD`で集め、リリースPull Requestでは`dev`をpushしない
- （作成者の仮定）`dev`以外のbranchから`main`へのPull Requestと、`main`をheadにしたPull Requestは、
  利用者が指定しても作らない。`main`から`dev`へ戻すmergeが要らない運用にするため
- （作成者の仮定）品質ゲートと`$review-kvk-change`の条件は、`dev`へのPull RequestとリリースPull Request
  の両方に適用する。リリースPull Requestのレビューは毎回初回のレビューとして扱い、保存ファイル名が
  毎回`dev`になっても前回のリリースの指摘、見送り、振り返りの回数を引き継がない。CIは従来どおり
  すべてのpushとPull Requestで実行する
- GitHubの既定branchを`dev`へ変え、`main`と`dev`にbranch保護を設定する。これはRepository管理者が
  GitHubの設定画面で行い、Agentは行わない
- （作成者の仮定）保護規則の内容は`DEVELOPMENT.md`の「ブランチ運用」に従う。Pull Requestを必須とし、
  運用者が1人のため必要な承認数は0とする。CIの4つのjobをすべて必須にし、force pushと削除を禁止し、
  管理者のbypassも許可しない。merge commitのメッセージはPull Requestのタイトルとする。
  「Require branches to be up to date before merging」と「Require linear history」は有効にしない。
  前者は`main`にだけ加わるmerge commitのために2回目以降のリリースを止め、後者はmerge commitを拒否する
- （作成者の仮定）GitHub Pagesで`web/`を公開している場合、公開元は`main`のままとし、利用者が使う画面も
  リリース済みの版にする

## 代替案

- **`main`だけのGitHub Flowを続ける**: 最も単純だが、統合中の変更とリリース済みの版を分けられず、
  利用者の求めに合わない。
- **git-flowの`hotfix/*`を`main`から分ける**: 緊急の修正を`dev`の未リリースの変更と切り離せるが、
  `main`から`dev`へ戻すmergeが必要になり、戻し忘れで`dev`と`main`が食い違う。利用者は`dev`を
  経由する方式を選んだ。代わりに、緊急の修正では`dev`にある未リリースの変更も一緒に`main`へ出る。
- **リリースをsquashで取り込む**: `main`の履歴は1リリース1コミットになるが、`dev`と`main`の
  履歴が分岐し、次回以降のリリースで同じ変更が衝突する。
- **`release/*`branchを設ける**: リリース前の調整期間が要らない規模のため、現時点では採らない。

## 影響

- `AGENTS.md`、`DEVELOPMENT.md`、`README.md`、`CLAUDE.md`、`$create-github-pr`、`$implement`を変える。
  `$review-kvk-change`と`$implement`の「基準ブランチ」は、Pull Requestのbaseを指すため、作業branchでは
  `dev`、リリースPull Requestでは`main`になる
- 既定branchを`dev`へ変えると、Repositoryのページと`git clone`が渡すのは`dev`になる。運用者が
  統合中の版を使わないよう、READMEで`main`を使うよう案内する
- Claude CodeのEnterWorktreeは`origin/<既定branch>`から作り、既存の複製の`origin/HEAD`はGitHubの
  既定branchを変えても追従しない。移動後は常に`$implement`の「Session用worktreeへ移る」の手順2で
  選んだコミット（元が`main`か`dev`なら`origin/dev`、それ以外は元のHEAD）と比べ、既定branchを変えた後の既存の複製では
  `git remote set-head origin --auto`を実行する
- 既存のopen Pull Requestのbaseが`main`のままであれば、`dev`へ変更する
- `web/`の修正は、`dev`へ取り込んだだけでは公開されず、リリースPull Requestの後に公開される
- 導入では、`dev`を作った後、最初のリリースPull Requestより前に保護規則とmerge方式を設定する。
  既定branchは、この変更を`dev`へ取り込み、最初のリリースPull Requestで`main`へ出した後に変える
- リリースPull Requestを作る手間が増える代わりに、`main`は品質ゲートとレビューを通した版になる
