# 開発ガイド

この文書は、WindowsとLinuxで同じ開発フローを再現するための手順です。開発上の
判断基準は [`AGENTS.md`](AGENTS.md) を参照してください。

## 対応環境

- Windows 11
- 一般的なLinux環境
- Python 3.11、3.12
- Node.js（`.node-version`に書いた版。`web/`のHTMLの検査に使う。ADR 0030）

パス操作と品質チェックはPythonで実装し、Bash、PowerShell、Makeのいずれにも
依存しません。

## WindowsのDocker DesktopとDev Containers

Windowsローカル開発では、Docker Desktop上のLinux Dev Containerを推奨します。Windows用の
Pythonへ個別に依存を入れる必要がなく、Container内でLinuxと同じ品質ゲートを実行できます。

事前にDocker DesktopのLinuxエンジンと、VS CodeのDev Containers拡張機能を用意してください。
Docker DesktopにはWSL 2とBIOS／UEFIの仮想化有効化が必要ですが、Ubuntuなど利用者向けのWSL
ディストリビューションは必要ありません。Docker Desktopが起動したことを次で確認します。

```powershell
docker version
docker run --rm hello-world
```

同期Folderを避けた場所へRepositoryをcloneし、VS Codeで開いてからコマンドパレットの
`Dev Containers: Reopen in Container`を実行します。ContainerにはNode.jsとnpmが入っており、
初回作成時に`.[dev]`と、`npm ci`でjsdomを自動で導入します。Container内のTerminalで次を実行し、
開発環境を確認してください。

```text
node --version
python tools/check.py
```

Node.jsを加える前（ADR 0030より前）に作成したContainerにはNode.jsがなく、品質ゲートが
「Node.jsが見つかりません」で失敗します。`Dev Containers: Rebuild Container`で作り直してください。
Windowsから共有した作業ツリーでは`node_modules/`の読み込みが遅く、`web/`の検査に数十秒かかることがあります。

Windowsから共有した作業ツリーはContainer内でroot所有に見え、そのままではGitが「dubious
ownership」で停止します。Containerは起動のたびに`postStartCommand`で
`sudo /usr/local/bin/fix-workspace-owner`を実行し、`/workspaces`直下の作業ツリーと`.git`の
所有者を実行利用者の`vscode`へそろえます。`safe.directory`による例外は設定しません。sudoで
許可されるのは引数なしのこのScriptだけで、他のコマンドはroot権限で実行できません。この変更より
前に作成したContainerは`Dev Containers: Rebuild Container`で作り直してください。

`.devcontainer/`はDocker socket、privileged設定、ポート公開、`GH_TOKEN`などの認証情報を
Containerへ渡しません。PRとIssueのGitHub CLI認証は、必要になった時点でホスト側またはContainer内で
別途行い、認証情報をRepositoryやイメージへ保存しません。

ContainerにはCodex、Claude Code、Python、Pylance、RuffのVS Code拡張機能を自動で導入します。
Codexは`OpenAI.chatgpt`、Claude Codeは`anthropic.claude-code`拡張機能として導入されます。
拡張機能だけは
`kvk-vscode-extensions`というDocker volumeで同じDocker Desktop上のDev Container間に
再利用されます。volumeはGit管理されず、別PCへの移行対象でもありません。拡張機能に問題がある場合は、
対象Containerを停止してからDocker Desktopでこのvolumeを削除し、Containerを再作成してください。

CodexとClaude Codeのログイン状態や他の認証情報は共有volumeに含めません。VS Codeまたは
各エージェントの案内に従って、
利用者ごとに認証してください。

## セットアップ

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
npm ci
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
npm ci
```

`npm ci`の前に、`.node-version`に書いた版のNode.jsを入れてください。公式サイトの
インストーラー、またはnvmやfnmなどの版管理ツールを使えます。`npm ci`は`package-lock.json`の
とおりにjsdomを`node_modules/`へ入れます。Node.jsまたはjsdomがない環境では、品質ゲートは
入れ方を示して失敗します（ADR 0030）。

## 品質チェック

ローカルとCIは同じコマンドを使用します。

```text
python tools/check.py
```

このコマンドは次を順に実行し、1つでも失敗すると非0で終了します。

1. Claude Code設定の同期の確認
2. Ruffフォーマット確認
3. Ruff Lint
4. mypy型検査
5. pytest全テスト
6. `web/`の集結タイムライン計算と周期ウェーブタイマーを、Node.jsとjsdomで実物のまま動かす検査
   （`tools/check_web.py`、`tests/web/`）

自動修正できるフォーマットとLintを適用してから全チェックを行う場合は、次を実行します。

```text
python tools/check.py --fix
```

`--fix`による変更は必ずレビューし、その後に表示されるテスト結果まで確認してください。

### 生成結果の確認

編成または表示を変更した場合は、テスト成功に加えて実際の出力を読みます。変更前と変更後に
次を実行すると、自己チェック、警告詳細、前回の出力との差分が表示されます。

```text
python tools/preview_output.py
```

既定では`sample/参加者一覧.md`を入力にし、Git管理外の`tmp/preview/チーム編成.md`へ書きます。
直前の出力は`チーム編成.previous.md`へ退避されます。`--input`、`--output`、`--seconds`で
入力、出力先、最適化の制限時間を変更できます。CP-SATは制限時間内の探索結果を返すため、
差分は確認材料として扱い、合否は自己チェックと品質ゲートで判断します。

## テストの責務

| 対象 | 主な検証内容 |
|---|---|
| `tests/test_parser.py` | 日本語入力記法、時間、属性、入力エラー |
| `tests/test_time_slot_optimizer.py` | CP-SATの必須制約、目的関数、決定性、解なしと時間切れの区別 |
| `tests/test_dynamic_validator_exporter.py` | 独立検証、警告、Markdown出力 |
| `tests/test_validator_properties.py` | 生成した編成で、必須条件を1つ破った候補の拒否と有効な編成の受理 |
| `tests/test_optimizer_properties.py` | 生成した参加者でのOptimizer出力の独立検証 |
| `tests/test_service.py` | Adapter調整、再試行、失敗伝播 |
| `tests/test_cli.py` | UTF-8ファイル入出力と終了コード |
| `tests/test_integration.py` | 実運用サンプルを使った一連の処理 |
| `tests/test_preview_output.py` | 生成結果の要約、差分、前回出力の退避 |
| `tests/test_agent_hooks.py` | Git保護と共有記憶のAgent Hook |
| `tests/test_web_tool_checks.py` | Node.jsの版の固定、jsdomのlockfile、CIとDev Containerの手順、`tools/check_web.py`の失敗時の案内 |
| `tests/web/*.test.js` | `web/`の実物のHTMLをjsdomで操作し、集結タイムライン計算の計算規則（`siege-timeline.md`の性質C1〜C9）、タブ、保存、周期ウェーブタイマーの計測と読み込みを検査 |

CP-SATを含むため全テストには数十秒かかります。変更中は対象テストを実行しても
構いませんが、完了前には必ず `python tools/check.py` を実行します。

CP-SATを実行するテストは`tests/deterministic_solver.py`の`deterministic_rules()`を使います。
実時間の制限や並列探索は、Runnerの負荷で結果が変わるため使いません（ADR 0019）。

性質テストはHypothesisで入力を生成します。`tests/conftest.py`のProfileが入力の固定
（`derandomize=True`）、失敗例の非保存（`database=None`）、制限時間なし（`deadline=None`）を
テスト全体へ適用します。同じHypothesisの版でテスト全体を実行すれば、手元とCIで同じ入力に
なります。版は範囲で指定しているため、手元とCIで版が異なると入力の並びも変わります。
テストを一部だけ実行した場合も、生成に使われる定数の候補が変わり、入力が異なることがあります。
テストごとに`@settings`で決定性の設定を上書きしたり、`@seed`を付けたりしないでください。
構造テストが検出します。生成戦略は
`tests/team_plan_strategies.py`にあり、必須条件を満たす編成を構成的に作ります。CP-SATを
実行する性質テストは生成件数を絞ります。失敗時は縮小された最小の入力と、
`@reproduce_failure`の再現用コードが表示されます（ADR 0025）。

## 設計判断の残し方

次の変更では `docs/adr/` にADRを追加します。

- 必須条件、警告、目的関数の区分変更
- レイヤー間の依存方向変更
- 永続化方式、UI方式、最適化方式の変更
- 対応PythonまたはOSの変更
- 新しい主要依存関係の導入

テンプレートをコピーして連番を付け、採用しなかった案と影響も簡潔に記録します。

### DDD配置チェック

新しいClassやRuleを追加する前に、次を確認します。

- 業務用語と意味が`docs/domain-model.md`に一致している
- 外部I/Oを知らずに表現できるルールはドメインへ置いている
- ユースケースの順序制御はアプリケーションへ置いている
- Markdown、JSON、CLI、OR-Tools固有処理はアダプターまたはインフラストラクチャへ置いている
- ドメインから外側への依存を追加していない
- エンティティ、Repository、ドメインイベントを形式だけで追加していない

現在は段階移行中です。パッケージ移動だけの変更と機能変更を分け、各段階で
`python tools/check.py`を成功させます。

### 文書の日本語ルール

リポジトリ内の説明文は日本語で記述します。コード識別子、パス、コマンド、設定キー、
製品名、ライブラリ名は公式表記を維持し、周囲の説明を日本語にします。スキルの`name`や
TOMLのフィールド名は変更せず、`description`、既定プロンプト、指示本文を日本語にします。

文書を変更した場合は、英語だけの見出しや段落が残っていないかレビューします。技術用語の
訳語は[ドメインモデル](docs/domain-model.md)と既存文書へ合わせ、新しい同義語を増やしません。

コミットメッセージは`type(scope): 日本語の要約`を基本形とします。自動分類や変更履歴の
検索に使うConventional Commitsの`type`と任意の`scope`は英語のまま維持し、要約と本文は
日本語で簡潔に記述します。

## AIエージェント（CodexとClaude Code）

CodexとClaude Codeのどちらでも同じ規約、スキル、レビュー観点で開発できます。正本と
各エージェントが読み込む場所は次のとおりです。

| 種類 | 正本（Codexが直接読む） | Claude Codeが読む場所 |
|---|---|---|
| 開発規約 | `AGENTS.md` | `CLAUDE.md`（`@AGENTS.md`を取り込む） |
| スキル | `.agents/skills/` | `.claude/skills/`（生成物） |
| レビューエージェント | `.codex/agents/*.toml` | `.claude/agents/*.md`（生成物） |

`.claude/skills/`と`.claude/agents/`は直接編集しません。正本を変更したら次を実行し、
正本と生成物を同じ変更に含めます。`python tools/check.py`は同期のずれを検出すると失敗し、
`--fix`は同期も行います。

```text
python tools/sync_agent_config.py
```

Codex専用の`$codex-handoff`と`$git-guardrails-codex`はClaude Codeへ同期しません。
Codexが解釈しないClaude Code専用の起動設定は、正本のFrontmatterへ書かず、
`tools/sync_agent_config.py`の`CLAUDE_SKILL_SETTINGS`から生成物へ加えます。既定と異なる
ToolのReview Agentは`CLAUDE_AGENT_TOOLS`で指定します。
Claude Codeでは、以下の`$skill-name`を`/skill-name`に読み替えます。
`.claude/settings.local.json`と、ローカルのプレビュー起動設定`.claude/launch.json`は、利用者ごとの
設定としてGit管理しません。

### Claude CodeのHook

`.claude/settings.json`は手で管理する共有設定であり、同期Scriptの生成物ではありません。
次のHookを登録しています。Hookは`tools/hooks/`のPython Scriptをexec形式で起動するため、
`python`をPATHから実行できる必要があります。

| Event | Script | 動作 |
|---|---|---|
| `PreToolUse`（Bash、PowerShell） | `block_dangerous_git.py --ask-push` | 強制push、`reset --hard`、`worktree remove --force`などを拒否し、通常のpushは利用者に確認する |
| `PreToolUse`（Bash、PowerShell、Monitor、編集Tool、Agent、MCP） | `enforce_read_only_agent.py` | `.codex/agents/`で読み取り専用と宣言したAgentに、許可した確認コマンドだけを通す。主Sessionと他のAgentは判定しない |
| `SessionStart` | `project_memory_hook.py session-start` | 共有記憶の開始状態を保存し、session_idと、別Sessionが使用中ならworktreeへ移る指示をContextへ渡す |
| `Stop` | `project_memory_hook.py stop` | 未記録の変更があれば1 Sessionに1回だけ`finish`を促す |

Git保護Scriptは`$git-guardrails-codex`でCodexへ設定するScriptと同じものです。保護対象を
変更する場合は`tools/hooks/`と`tests/test_agent_hooks.py`を同時に更新します。共有記憶Hookは
失敗しても作業を止めず、理由を標準エラーへ出します。Claude Codeは信頼したWorkspaceでだけ
Project Hookを実行します。一時的に無効化する場合は、利用者ローカルの設定で
`disableAllHooks`を使用します。

`.claude/settings.json`の`permissions.deny`は、生成物である`.claude/skills/`と`.claude/agents/`の
直接編集と、`.env`の読み取りを拒否します。拒否されるのはClaude Codeの編集・読み取りToolだけで、
`python tools/sync_agent_config.py`による生成は従来どおり動作します。

Subagentの`permissionMode: plan`は、親Sessionが`auto`、`acceptEdits`、`bypassPermissions`のとき
無視されます。`enforce_read_only_agent.py`はHook入力の`agent_type`で対象を判定し、Review Agentの
Bashでは、`git`の読み取り系サブコマンド、`cat`や`grep`などの読み取りコマンド、`pytest`、
`tools/check.py`、`tools/sync_agent_config.py --check`だけを許可します。ファイルへのリダイレクト、
コマンド置換、`--fix`などの書き込みOptionは拒否します。`tools/preview_output.py`は`tmp/preview/`の
前回出力を上書きするため、Review Agentからは実行できません。Hookの変更は新しいSessionから
有効になります。

### 共有スキル

リポジトリには次の共有スキルがあります。

```text
$review-kvk-change
$change-kvk-rules
$apple-design
$create-github-pr
$manage-github-issue
$maintain-project-memory
$implement
$change-ai-harness
$research
```

`$review-kvk-change`は、`.codex/agents/`（Claude Codeでは`.claude/agents/`）にある
ドメイン、アーキテクチャ、テスト、要件の読み取り専用sandboxを要求する4つのレビューエージェントを
束ねます。レビュー対象のブランチ、
コミット、
または差分をプロンプトで指定してください。指定がない場合は現在の作業ツリーとブランチ
差分を対象にします。実行環境が名前付きエージェントまたは読み取り専用sandboxを適用
できない場合、主エージェントが同じ4つの観点を順に確認します。要件レビュー担当
（`kvk-requirements-reviewer`）は、出典との一致、考慮漏れ、曖昧さ、矛盾を確かめます。文書だけの
変更もレビューの対象です。理由を書けばレビューを見送れるのは、意味を変えない誤字の修正だけの変更、共有記憶（`docs/project-memory/`）だけの変更、意味を変えない誤字の修正とそのセッションの共有記憶の記録だけを含む変更の3つです（ADR 0024）。結果はテンプレートの形式で
`tmp/reviews/`へ保存され、対象branchのPull Requestへコメントとして投稿されます（ADR 0022）。
指摘へ対応した後は再レビューし、`$review-kvk-change`の終わる条件を満たすまで繰り返します（ADR 0024）。
レビューでは常に`python tools/review_fingerprint.py --base <head>`で変更の指紋を記録し、投稿、Ready、
pushの後の投稿のときに、コミット後の範囲と照合して同じ版かを確かめます。

`$change-kvk-rules`は、ルールを必須条件、警告、目的関数、入力正規化、表示のいずれかへ
分類してから変更する手順です。

`$change-ai-harness`は、Skill、Review Agent、Agent Hookを変更するときに、正本、生成物、
`tests/test_ai_harness.py`、規約文書、ADRをそろえる手順です。項目別の確認は同Skillの
`references/checklist.md`にあります。

`$implement`は、合意済みの仕様やTicketを`AGENTS.md`の完了条件まで実装する手順です。完了条件を
先に書き、複数Sessionにまたがる作業ではGit管理外の`tmp/progress/`に進捗ファイルを置いて
中断と再開を管理します。コミットやpushは利用者が明示した場合だけ行います。CodexまたはClaude Codeがスキルを認識しない場合は、
リポジトリ直下からセッションを開始し直してください。

同じ作業ツリーを別Sessionが使用中の場合、`$implement`はSession専用のworktreeとbranchへ移って
から編集します。Codexでは`.worktrees/`へ`git worktree add`で作成し、Claude Codeでは
EnterWorktree Toolで`.claude/worktrees/`へ作成します。どちらもGitの除外対象です。完了後の
コミット、統合、worktreeの削除は利用者が明示した場合だけ行います。

`$research`は、一次情報を開いて主張ごとに`verified`、`incorrect`、`unresolved`を判定し、出典URLと
確認日を付けた下書きをGit管理外の`tmp/research/`へ書く手順です。読み取り専用の
`evidence-reviewer`が下書きの各主張を出典と照合し、訂正を反映してから報告します。Repositoryの
`docs/research/`などへ保存するのは、利用者が保存を求めた場合だけです。SNSや記事の主張は
手掛かりとしてだけ扱います。

`$apple-design`は、Web UIの目的と状態を整理し、即時Feedback、中断可能なInteraction、
文字組み、レスポンシブ対応、低モーションを含むアクセシビリティを一体で設計・確認する
手順です。UIだけへ編成ルールを複製せず、アプリケーション境界を通して実装してください。

`$create-github-pr`は、現在branchとbase branchの差分、Pull Requestテンプレート、検証結果から
タイトルと本文を作成し、重複を確認してGitHubへ公開する手順です。Codespacesでは
Codespaces Secretの`GH_TOKEN`を使用し、TOKENをファイルへ保存または表示しません。Projectの
`Hierarchy`項目も操作する場合は、`gh auth login --web --scopes "project,read:org,workflow"`で
ログインします。許可するスコープと有効期限はADR 0008に従ってください。本文の準備だけを
依頼した場合は外部作用を行わず、Pull Request作成が明示された場合だけ通常pushと作成を行います。

`$manage-github-issue`は、既存IssueとTemplateを確認して単一Issueを作成するか、指定された単一Issueを
完全削除する手順です。削除では対象を再取得し、Pull RequestではないことをAPIで確認してから、番号、
題名、URL、復元不能であることを提示します。その提示後に同じ対象の削除が再承認されるまで、
`gh issue delete`を実行しません。解決済みの作業には削除よりCloseを検討してください。

## プロジェクト共有記憶

`$maintain-project-memory`は、機能実装またはRepository変更を行うSessionの開始状態と終了状態を
比較し、そのSessionによる有効な差分がある場合だけ`docs/project-memory/`へ記憶を作成します。
開始前から存在する利用者差分、共有記憶自身、Gitの除外対象は判定から外します。

変更作業の編集前に次を実行し、出力された`session_id`を保持します。Claude Codeでは
SessionStart Hookが自動で実行し、session_idをContextへ渡すため、手動実行は不要です。

```text
python .agents/skills/maintain-project-memory/scripts/session_memory.py start
```

`start`の出力で`use_separate_worktree`が`true`の場合は、同じ作業ツリーで最後の操作から3時間以内の
別Sessionがあります。変更作業ではSession用worktreeへ移り、元の開始状態を`discard`で破棄してから
移動先で`start`を実行します。

実装と対象Checkを終えた後、`finish --help`で引数を確認し、依頼、結果、判断、検証、未完了事項を
指定して終了処理を実行します。変更がない調査、相談、説明、読み取り専用Reviewでは実行しません。
利用者が明示的に記録を依頼した場合は`--force`を指定できます。

```text
python .agents/skills/maintain-project-memory/scripts/session_memory.py finish --help
```

手作業で記憶または昇格候補を変更した場合は、次を実行します。

```text
python .agents/skills/maintain-project-memory/scripts/session_memory.py rebuild-index
python .agents/skills/maintain-project-memory/scripts/session_memory.py validate
```

`finish`は、既定タグ以外の同じタグを持つ記憶が3件以上になると`promotion_hints`を返します。
これは見直しのきっかけであり、記憶を読んで反復を確認するまで候補を作りません。

独立した複数Sessionで同じ手順、失敗、判断が現れた場合は昇格候補へ根拠を追加します。候補の
検出だけでは`AGENTS.md`やSkillを変更しません。利用者が昇格を承認した後、対象を通常の変更として
実装・検証し、候補を`promoted`へ更新して正本のパスを`promoted_to`へ記録します。詳細なSchema、
昇格先、秘密情報の扱いは[プロジェクト共有記憶](docs/project-memory/README.md)を参照してください。

## ブランチ運用

`main`はリリース済みの版、`dev`は次のリリースへ向けた統合branchです（ADR 0027）。

```text
作業branch --PR--> dev --リリースPR（merge commit）--> main
```

- 作業branchは`git fetch origin dev`の後に`origin/dev`から作り、`dev`へPull Requestを出します。
  `$create-github-pr`はbaseを省略すると作業branchでは`dev`、`dev`では`main`を使います
- `main`へは`dev`からのリリースPull Requestだけをmerge commitで取り込みます。squashやrebaseは
  使いません。`dev`のコミットはすべて`main`の祖先に含まれ、`main`にはリリースのmerge commitだけが
  加わります
- 緊急の修正も`dev`を経由し、取り込んだ直後にリリースPull Requestを作ります
- `main`と`dev`へ直接コミットまたはpushしません。導入時に`main`から`dev`を作る最初の通常pushだけが
  例外です
- CIは`main`と`dev`へのpushと、すべてのPull Requestで実行します。Pull Requestを作る前の作業branchの
  pushでは実行しないため、手元の`python tools/check.py`で確かめます。（作成者の仮定）Pull Requestを
  作る前にCIで確かめたい場合は、利用者が明示したときに`$create-github-pr`でDraft Pull Requestを作ります。
  同じPull Requestへ続けてpushすると、古い実行は中止されます。ほかのPull Requestやpushの実行は
  中止されません。`dev`へのpush、リリースPull Request、取り込んだ後の`main`へのpushは同じ内容を
  検証するため、リリースごとに3回実行されます（ADR 0028）
- 利用者が運用に使うのは`main`です。READMEの手順もこれに合わせています

導入時の手順は次のとおりです。番号の順に行います。手順1はClaude CodeのAgentが利用者の確認を得て
行えます。Codexではpushを拒否する設定のため、利用者が行います。手順2以降のGitHubの設定は
Repository管理者が設定画面で行い、Agentは行いません。手順2と手順3は、最初のリリースPull Requestを取り込む前に
済ませます。

1. `origin`に`dev`がない場合だけ、`git fetch origin main`の後に
   `git branch --no-track dev origin/main`で`dev`を作り、`git push --set-upstream origin dev`で
   通常pushする。手元の`main`は古いことがあるため、`origin/main`から作る
2. Settings > Branchesで`main`と`dev`へ保護規則を加え、次を設定する
   - 「Require a pull request before merging」を有効にし、その中の「Require approvals」は有効にしない
     （運用者が1人で、自分のPull Requestを承認できないため。rulesetsでは必要な承認数を0にする）
   - 「Require status checks to pass before merging」を有効にし、`ubuntu-latest / Python 3.11`、
     `ubuntu-latest / Python 3.12`、`windows-latest / Python 3.11`、`windows-latest / Python 3.12`の
     4つをすべて必須にする（workflow名の「品質チェック」は選べない）
   - force pushと削除を許可しない
   - 「Require branches to be up to date before merging」は有効にしない。`main`にはリリースの
     merge commitが加わり`dev`に戻らないため、有効にすると2回目以降のリリースPull Requestが止まる
   - 「Require linear history」は有効にしない。merge commitを拒否するため
   - 「Do not allow bypassing the above settings」を有効にし、管理者の直接pushも止める
3. Settings > Generalで「Allow merge commits」を有効にし、その「Default commit message」を
   「Pull request title」にする。リリースPull Requestのタイトルを`type(scope): 日本語の要約`で書けば、
   `main`へ加わるmerge commitもコミットメッセージの規約に合う。リリースPull Requestは
   「Create a merge commit」で取り込む
4. GitHub Pagesで`web/`を公開している場合は、公開元をSettings > Pagesで`main`のままにする。
   `web/`の修正は`dev`へ取り込んだだけでは公開されず、リリースPull Requestの後に公開される
5. この変更（ADR 0027）を`dev`へ取り込み、最初のリリースPull Requestで`main`へ出した後に、
   Settings > General > Default branchを`dev`へ変える。READMEの`main`を使う案内が`main`に載る前に
   既定branchを変えないためである。変えた後、既存の複製の利用者がそれぞれ
   `git remote set-head origin --auto`を実行し、`origin/HEAD`を`origin/dev`へ合わせる

## プルリクエストの単位

1つのPull Requestでは、1つの利用者価値または1つの技術的目的を扱います。機能変更と
無関係な大規模整形、名前変更、依存更新を混在させません。Pull Requestテンプレートの
チェック項目を満たし、生成したMarkdownに運用上必要な警告が残ることを確認します。
