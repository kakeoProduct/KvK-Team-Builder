# ADR 0018: Review Agentの読み取り専用をPreToolUse Hookで強制する

- 状態: 採用
- 日付: 2026-10-17

## 背景

Claude CodeのSubagentは、親Sessionが`auto`、`acceptEdits`、`bypassPermissions`のとき、親と
同じ権限モードで動く。この場合、定義した`permissionMode: plan`は無視される。Review Agentは
編集Toolを持たない。しかし`Bash`を持つため、autoモードの`kvk-test-reviewer`は`touch`と
リダイレクトでファイルを作れた。Codexの`sandbox_mode`も、親Sessionの権限で上書きされ得る。

公式文書によると、PreToolUse Hookによる拒否は権限ルールと権限モードより先に評価される。また、
Subagent内のTool呼び出しでは、Hook入力に`agent_type`が入る。

## 判断

- `tools/hooks/enforce_read_only_agent.py`を`.claude/settings.json`のPreToolUseへ登録する。
  matcherは書き込み得るTool（`Bash`、`PowerShell`、`Monitor`、`Edit`、`Write`、
  `NotebookEdit`、`Agent`、`mcp__.*`）に限る。読み取りToolと内部Toolでは起動しない
- 対象は、Hook入力の`agent_type`が`.codex/agents/<名前>.toml`と一致し、その定義が
  `sandbox_mode = "read-only"`を宣言するAgentだけとする。主Sessionと他のAgentは判定しない。
  読み取り専用の宣言を正本の1か所に保ち、Hook側に一覧を複製しない
- 対象のAgentでは、Hookへ届いたToolのうち、許可リストに一致するBashコマンドだけを通し、
  それ以外を拒否する。使えるToolの範囲は、生成するAgent定義の`tools`で絞る
- Bashで許可するのは、`git`の読み取り系サブコマンド、読み取りコマンド、`pytest`、
  `tools/check.py`、`tools/sync_agent_config.py --check`である。ファイルへのリダイレクト、
  コマンド置換、改行、環境変数の上書き、書き込みOption、解析できない入力は拒否する
- `tools/preview_output.py`は既定でも`tmp/preview/`の前回出力を上書きし、利用者の差分の基準を
  失わせる。このため、Review Agentからの実行を許可しない
- `pytest`はGit管理外のCacheと一時Directoryへ書き込むが、追跡対象を変更しないため許可する。
  厳密な`plan`より広い。しかし、`kvk-test-reviewer`が疑わしい問題をテストで確かめる責務を
  優先する

## 代替案

### 全ToolをHookの対象にし、内部Toolを許可リストで通す

未知のToolも拒否できる。しかし、主Sessionの読み取りを含む全Tool呼び出しでPythonが起動する。
また、Claude Codeが内部Toolを増やすと、対象Agentが結果を返せなくなる。実際に`SubagentHandback`
を拒否し、報告が届かなかった。対象Agentの`tools`で使えるToolは絞られているため、未知のToolを
拒否する利点は小さい。

### Subagentを一時的なworktreeで動かす

`isolation: worktree`のworktreeは、既定branchから作られる。作業中のbranchと未コミットの差分が
見えず、レビュー対象を読めない。

### autoモードと`bypassPermissions`を無効にする

`acceptEdits`は防げず、利用者がautoモードを使えなくなる。

### Subagent定義のFrontmatterへHookを書く

対象Agentの実行中だけ動き、範囲は最も狭い。しかし、生成した定義へ登録しても、新しいSessionで
発火しなかった。このため採用しない。

### Review AgentからBashを外す

最も確実である。しかし、差分の確認（`git diff`）とテストによる裏取りができなくなり、
レビューの質が下がる。

### 拒否リストで書き込みコマンドを止める

通常のコマンドは妨げない。しかし、書き込み得るコマンドとOptionは列挙しきれない。
解析できない入力を通してしまう。

### OSのsandboxを有効にする

Shellの子Processまで防げる。しかし、Session全体へ効くため、主Sessionの同期Scriptと
品質ゲートの書き込みも制限する。Subagentは親と同じsandbox設定を使い、Agentごとの設定は
できない。

## 影響

- 主Sessionでも、書き込み得るToolの呼び出しごとにPythonが1回起動する。対象外の呼び出しは、
  `agent_type`を確認してすぐに通す
- matcherにない新しい書き込みToolをClaude Codeが追加しても、Hookは検査しない。対象Agentの
  `tools`に加えない限り使われないが、`tools`を広げるときはmatcherも見直す
- 許可リストにない確認コマンドは、Review Agentから実行できない。必要になったら、Hookと
  `tests/test_agent_hooks.py`へ追加する
- Hookの追加と変更は、Claude Codeの新しいSessionから有効になる
- Codexには適用されない。Codexでは、従来どおり`sandbox_mode`と指示文で読み取り専用を守る
