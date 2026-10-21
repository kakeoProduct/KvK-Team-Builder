# ADR 0008: Codespaces認証によるGitHub Pull Request作成

- 状態: 提案中
- 日付: 2026-07-20
- 更新: 2026-10-17（個人所有のProjectを扱う認証方式、スコープ上限、有効期限を追加）

## 背景

GitHub Pull Requestの作成をCodexと人間で再現可能にするには、GitHub CLIの認証、差分の範囲、
品質ゲート、外部作用の承認を同じ手順で扱う必要がある。TOKENをRepository内の`.env`へ保存すると、
Gitの除外設定だけでは平文参照、誤送信、拡張機能や子Processからの取得を防げない。

Codespacesは開発環境Secretを環境変数として提供し、Repository accessを限定できる。現在の
RepositoryはCodespacesを主な開発環境として使用できるため、この境界を認証の標準とする。

2026-10-17の追記: Issueの親子関係と進捗は、個人アカウントが所有するProject「KvK Utility Tool」の
`Hierarchy`項目（`Epic`、`Child`）でも管理している。GitHubの公式文書は、fine-grained PATの制限として
個人アカウント所有のProjectsへアクセスできないことを挙げており、Projectsの権限はOrganization
permissionにしか存在しない。このため、Repository限定のfine-grained PATだけではProjectの項目を
読み書きできない。

## 判断

- Codespacesでは、対象Repositoryだけへアクセスできるfine-grained PATをCodespaces Secretの
  `GH_TOKEN`として提供する
- PATには有効期限を設定し、Pull Request、Issue、開発時の読み取りなど、実際に必要なRepository
  permissionだけを付与する
- TOKENを`.env`、Skill、Script、Git設定、Pull Request本文、会話へ保存または表示しない
- `$create-github-pr`は`gh auth status`と読み取り専用APIで認証を確認し、認証または権限を確認
  できない場合は外部作用を行わない
- 本文準備の依頼ではpushとPull Request作成を行わず、作成の明示を通常pushと`gh pr create`の
  承認として扱う
- force push、merge、Issue操作をPull Request作成の暗黙の権限へ含めない
- Codespaces以外では既存のGitHub CLI認証を利用し、Repository固有の認証情報を追加しない

### 個人所有のProjectを扱う場合（2026-10-17追記）

- Projectを操作しない作業では、引き続きRepository限定のfine-grained PATを優先する
- Projectの項目を読み書きする場合に限り、次のどちらかを許可する
  - `gh auth login --web`で取得するGitHub CLIのOAuthトークン（推奨。TOKENを複写しない）
  - classic PAT
- スコープの上限は`repo`、`project`、`read:org`、`workflow`とする。`gh auth login --web`が既定で
  加える`gist`は許容する。`admin:*`、`delete_repo`、`write:packages`、`user`など、これ以外の
  スコープを付けない。Projectを読むだけなら`project`の代わりに`read:project`とする
- classic PATの有効期限は90日以内とし、「No expiration」を選ばない。OAuthトークンには有効期限が
  ないため、不要になったらGitHubの「Settings → Applications → Authorized OAuth Apps」から
  GitHub CLIの承認を取り消し、少なくとも90日ごとに要否を見直す
- 不要になった旧TOKENは失効させる
- GitHub CLIは認証情報を`~/.config/gh/hosts.yml`へ平文で保存する場合がある。Agentはこのファイルを
  読まず、`gh auth status`の`Token scopes`と伏せ字のTOKEN種別だけで認証を確認する

## 代替案

### `.env`へTOKENを保存する

導入は簡単だが、平文の長期認証情報をWorkspaceへ置き、Git除外、権限、誤表示を継続的に管理する
必要がある。Repository限定Secretより漏えい時の経路が多いため採用しない。

### GitHub CLIの対話Loginだけを使用する

Local PCでは資格情報Storeを利用できるが、Codespacesで安全なStoreが利用できない場合は平文Fileへ
fallbackする。CodespacesのRepository単位Secretを標準とし、Local環境の選択肢として残す。

### fine-grained PATだけを使い、Projectは画面で手動操作する

TOKENの範囲は最小になるが、Sub-issueとHierarchyの整合をAgentが確認できず、設定漏れが残る。
実際に2026-10-17、Hierarchyが未設定のIssueを検出できなかったため採用しない。

### ProjectをOrganization所有へ移す

fine-grained PATのOrganization permissionでProjectsを限定できるが、Organizationの作成と移行が
必要になる。個人運用の現状には過剰なため、共同運用者が増えたときに再検討する。

### GitHub Appを作成する

短命なinstallation tokenと組織的な権限管理を利用できるが、App登録、秘密鍵、token発行処理が
必要になる。単一Repositoryの対話的なPull Request作成には過剰なため、無人運用や複数Repositoryへ
拡大するときに再検討する。

## 影響

Codexと人間は同じPull Requestテンプレートと品質ゲートを使い、TOKENをRepositoryへ残さずに
Pull Requestを作成できる。Codespaces Secretの追加または更新後はCodespaceの停止と再開が必要に
なる。PATの期限切れ、権限不足、sandboxのNetwork制限は明示的な失敗として扱い、認証失敗と
接続失敗を区別する必要がある。

classic PATとOAuthトークンは特定のRepositoryへ限定できず、利用者がアクセスできる全Repositoryと
Projectが対象になる。漏えい時の影響はfine-grained PATより大きいため、スコープの上限、有効期限、
不要時の失効を運用で守る。
