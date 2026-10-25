# ADR 0030: Review Agentのモデルとターン上限を固定し、Codexでも読み取り専用と結果の形式を強制する

- 状態: 提案中
- 日付: 2026-10-25
- 置き換え: ADR 0002のうち、読み取り専用sandboxを適用できない場合に逐次レビューへ切り替えるとした点
  （切り替えの条件を、読み取り専用の強制を確かめられない場合に変える）。ADR 0008のうち、Pull Requestの
  作成の明示を、Agentによる通常pushの承認とする点（Codexでは利用者がpushする）。ADR 0017のうち、Codexでは
  本文の手順でSubagentの読み取り専用を守るとした点。ADR 0018のうち、Codexには適用せず`sandbox_mode`と
  指示文で読み取り専用を守るとした点

## 背景

AnthropicとOpenAIの公式文書と、OpenAIが公開するCodexのソース（`openai/codex`、2026-10-23の
`970111f`）を2026-10-25に確かめ、Review Agentの運用に次の問題が見つかった。利用者は、親Sessionを
Autoのまま使いたい。

公式文書で確かめたこと:

- Codexは、custom agentのTOMLに書いた`sandbox_mode`と`approval_policy`を適用しない。Subagentは
  親Sessionのsandboxと承認設定を継承する（`learn.chatgpt.com/docs/agent-configuration/subagents`）。
  ソースでも、ロールが適用する項目に`sandbox_mode`はない（`codex-rs/core/src/agent/role.rs`、PR #39299）
- CodexのHookは`.codex/hooks.json`に書け、作業Directoryで起動する。Project Hookは`.codex/`の層が
  信頼され、利用者が各Hookを`/hooks`で信頼するまで動かない。信頼は内容のHashへ記録される。
  Windowsでは`commandWindows`を使う。CodexのSubagentStopの入力には`agent_type`、`stop_hook_active`、
  `last_assistant_message`が入り、`decision: "block"`か、標準エラーがある終了コード2でSubagentに
  続きを書かせられる（`learn.chatgpt.com/docs/hooks`）
- Claude CodeのSubagentのモデルは、起動時の`model`引数、Frontmatterの`model`、
  `CLAUDE_CODE_SUBAGENT_MODEL`、主会話のモデルの順で決まる。どれも指定がなく主会話がOpusなら、
  5つのReview AgentはすべてOpusで動き、`effort`は`CLAUDE_CODE_EFFORT_LEVEL`が未設定ならFrontmatterの
  `high`になる。公式の費用指針は、
  多くの作業にSonnetを勧める。マルチエージェントは単一エージェントの3〜10倍のトークンを使う
- Claude CodeのSubagentStopも`decision: "block"`と`stop_hook_active`を持つ

ソースから読み取ったこと（公式文書には記載がない）:

- CodexのPreToolUseは、Subagent内のTool呼び出しでも、入力に`agent_id`と`agent_type`（ロール名）を
  入れる（PR #22882、2026-05-21。`codex-rs/core/src/hook_runtime.rs`の
  `thread_spawn_subagent_hook_context`）。公式文書の入力表には`agent_type`がない
- Codexは、Shellの種類を問わず`exec_command`を`tool_name: "Bash"`と`{"command": 文字列}`で渡す。
  編集は`apply_patch`、Agentの起動は`spawn_agent`として渡す（`codex-rs/core/src/tools/`）。Windowsの
  既定のShellはPowerShellで、モデルは`shell`引数でcmdも選べる
- CodexはUnixで`sh -lc`、Windowsで`cmd.exe /C`としてHookを起動する
  （`codex-rs/hooks/src/engine/command_runner.rs`）。PreToolUseのHookが0と2以外で終了するか、起動に
  失敗すると、拒否せずに続ける（`codex-rs/hooks/src/events/pre_tool_use.rs`）。SubagentStopで続きを
  書かせる回数に上限はない

このRepositoryで確かめたこと:

- 過去のReview Agentの実行120回では、最大が33ターン、担当ごとの中央値は12〜20ターンだった。
  `maxTurns`を40にした後の再レビューでは、アーキテクチャ担当が上限に達し、報告を返さずに止まった。
  続きの指示を送ると、それまでに確かめた内容の報告が届いた
- Claude CodeのSubagentは、最終報告を本文ではなく`SubagentHandback`の呼び出しで返している。
  このため、SubagentStopの`last_assistant_message`だけでは報告を読めない
- 読み取り専用の強制には、全OSで通る抜け道があった。shlexは語の途中の`#`以降を注釈として捨て、
  Gitとsortは長いOptionの省略形を受け付け、pytestは`-o addopts=...`で拒否したOptionを注入できる
- 主Sessionは、レビュー結果を`Must`、`Should`、`Nice`、`未確定`に分けて統合する。見出しが
  欠けた結果では、指摘なしと書き漏れを区別できない

## 判断

- `.codex/hooks.json`を追跡し、Claude Codeと共通のScriptを登録する
  - PreToolUseの`enforce_read_only_agent.py`。matcherは書き込み得るTool（`Bash`、`apply_patch`、
    `spawn_agent`、MCP）とする。読み取り専用の宣言は、従来どおり正本のTOMLの`sandbox_mode`を目印にする
  - PreToolUseの`block_dangerous_git.py`。Codexは確認（`ask`）を扱えないため、既定の動作で通常の
    pushも拒否する（ADR 0014）
  - SubagentStopの`check_review_report.py`
- Codexは作業Directoryで起動するため、`command`は`git rev-parse --show-toplevel`でScriptを解決し、
  `python3`で起動する。Windowsでは`commandWindows`で`for /f`を使って同じ解決をし、`python`で起動する。
  SubagentStopの`command`は、ルートを解決できたときだけPythonを起動し、終了コード2で続行を求めない
- `enforce_read_only_agent.py`は、`Bash`のコマンドをPOSIXのShellとして判定する
  - POSIXと解釈が食い違う記号は、記号ごとの書き方を並べず丸ごと拒否する。`{`と`}`（PowerShellの
    Script Block）、全角の引用符（PowerShellの解釈）、`$`（変数の展開でHookが見ていない引数を渡す）、
    `\`（PowerShellとcmdではエスケープにならず語の区切りが変わる）は常に、単一引用符、`^`、`%`と`!`（変数の
    展開。`!`は遅延展開が有効な場合）、`/`で始まる`sort`の引数（cmdの解釈）はWindowsで拒否する
  - shlexの注釈の処理を無効にし、語の途中の`#`以降も判定する
  - pytest、sort、findはOptionを許可リストで判定する。pytestは出力の量とテストの選択（`-q`、`-v`、`-x`、
    `-k`、`-m`、`--tb=`など）だけ、sortは並べ方（`-r`、`-n`、`-k`、`-t`など）だけ、findは検索の条件
    （`-name`、`-type`、`-maxdepth`など）、探索の制御（`-prune`、`-quit`、`-depth`）、出力（`-print`、`-ls`
    など）だけを通す。Claude Codeの`find`は
    bfsで、GNU findにない`-rm`（削除）を持つため、拒否リストでは防げない。pytestの`@file`（Optionを
    書いたファイル）は、値の位置でも拒否する
  - Gitの`--output`と`--open-files-in-pager`は省略形も、`-O`は`-nO<cmd>`のように束ねた短いOptionも
    拒否する。ripgrepの外部コマンドを起動する`--pre`と`--hostname-bin`も拒否する
- Review Agentのモデルを明示する。判断の重い担当（`kvk-requirements-reviewer`、
  `kvk-architecture-reviewer`、`evidence-reviewer`）は、Claude Codeで`opus`、Codexで`gpt-6.1-sol`と
  する。`kvk-domain-reviewer`と`kvk-test-reviewer`は、Claude Codeで`sonnet`、Codexで`gpt-6-luna`と
  する。Codexの値は正本のTOMLの`model`へ、Claude Codeの値は`tools/sync_agent_config.py`の
  `CLAUDE_AGENT_MODELS`から生成物へ書く。`model_reasoning_effort`（`effort`）は`high`のままとする。
  主エージェントはReview Agentの起動時に`model`引数を渡さない
- Claude Codeの`maxTurns`を、`kvk-domain-reviewer`、`kvk-test-reviewer`、`kvk-requirements-reviewer`で40、
  `kvk-architecture-reviewer`と`evidence-reviewer`で60とする。証拠の照合は下書きの主張の数に比例して
  長くなり、アーキテクチャ担当は40で足りなかった。Codexには同等の設定がない
- `check_review_report.py`は、4つのレビュー担当の結果に`## Must`、`## Should`、`## Nice`、`## 未確定`の
  見出しが、`evidence-reviewer`の結果に`| 主張 | 判定 | 出典URL | 確認日 | 必要な訂正 |`の列がなければ、
  欠けた行を示して書き直させる。各Agentの指示にも同じ見出しと列を書く
  - 報告は`last_assistant_message`と、`agent_transcript_path`の記録にある最後の`SubagentHandback`から
    読む。本文が形式を満たせば記録を読まない。どちらかが形式を満たせば通し、どちらからも報告を
    取り出せなければ止めない
  - `stop_hook_active`が真なら検査せずに返し、書き直しは1回までとする。補助的な検査のため、解析できない
    入力と対象外のAgentでは止めない
- （作成者の仮定）主Sessionは、4つのレビュー担当を起動する前と、`$research`を起動する前に、読み取り専用の
  強制が動いていることを確かめる。`$research`はSubagentとして動き利用者に尋ねられないため、主Sessionが
  確かめた結果を問いと一緒に渡し、`$research`は動いていると渡された場合だけ`evidence-reviewer`を起動する。
  確かめられない場合は、強制を適用できない環境として、レビューでは4つの観点を主Sessionが順に確認し、
  調査では`evidence-reviewer`を起動できない環境として扱う。利用者が`/research`で直接起動した場合は、
  主Sessionの確認が挟まらず結果が渡らないため、独立検証をせず、そのことを報告に書く。独立検証が要る調査は
  主Sessionに依頼する。Claude Codeでは、SessionStart HookのContextが届いていれば
  Project Hookが動いているとみなす。Codexでは、利用者が`/hooks`でHookを信頼済みと答えた場合だけ並列に
  委譲する。どちらの場合も親SessionはAutoのままでよい
- （作成者の仮定）`maxTurns`で止まった担当には、続きの指示で報告をまとめさせる。それでも見出しが
  欠けた結果は不完全とみなし、主Sessionがその観点を定義に従って確認し直し、レビュー結果の
  「前提と未実行の検査」に書く。`evidence-reviewer`の結果で判定表の列がないか、下書きの一部の主張にしか
  判定がない場合は、判定のない主張の出典を`$research`を実行するAgentが開き直し、独立に検証できなかった
  主張として報告する
- （作成者の仮定）CodexではGit保護Hookが通常のpushを拒否するため、`$create-github-pr`と`$implement`は
  pushのコマンドを利用者に示して実行を頼み、`origin/<branch>`がpush済みであることを確かめてから続ける

## 代替案

### Codexでレビューするときは親Sessionを読み取り専用で起動する

Codexの公式文書が示す方法で、OSのsandboxが子Processまで防ぐ。しかし、利用者はAutoのまま
使いたい。レビューのたびに起動し直す必要があり、レビュー後の修正と同じSessionで進められない。

### Git保護HookをCodexでは利用者ごとの設定に任せる

`$git-guardrails-codex`で利用者が設定する従来の方法で、既定ではpushを妨げない。しかし、追跡する
`.codex/hooks.json`と手順が食い違い、ADR 0014で両Agentに共有するとした保護が人によって欠ける。
利用者は登録する案を選んだ。

### 全担当を`opus`（`gpt-6.1-sol`）にする

現在と同じ品質を固定できる。しかし、ドメインとテストの担当まで上位モデルを使い、費用が下がらない。
利用者は重い担当だけを上位モデルにする案を選んだ。下位モデルの担当で見落としが増えた場合は、この
判断を見直す。

### `maxTurns`を5にする、または全担当を40にそろえる

5では過去の実行のほとんどが打ち切られる。40にそろえると、アーキテクチャ担当が再レビューで上限に
達した。利用者はアーキテクチャ担当を60にする案を選んだ。

### 結果の形式を指示文だけで求める

Hookを足さずに済む。しかし、指示は守られないことがあり、欠落を主Sessionが読むまで気付けない。
SubagentStop Hookは決定的に検査し、正しい結果ではトークンを使わない。

### Subagent定義のFrontmatterへHookを書く

Claude Codeでは、Agentファイルのあるフォルダそのものを信頼したときだけ動き、`claude -p`では
動かない。Codexのcustom agentにはHookの項目がない。共有の強制には設定ファイルのHookのほうが確実である。

## 影響

- CodexでもAutoのままReview Agentを読み取り専用で動かせる。ただし、利用者が`/hooks`でHookを
  信頼するまでは強制されない。Hookを変更したら信頼し直す
- CodexのPreToolUseの`agent_type`はソースだけに基づき、Codexの実機（WindowsとLinux）では確かめて
  いない。Codexの更新で入力が変わると、Hookは対象を判別できずに通す。版を上げたら、`/hooks`の一覧と、
  Review Agentに書き込みを試させた結果を確かめる
- Hookの起動に失敗したときの挙動はOSとEventで違う。Claude Codeも、0と2以外の終了を拒否として扱わない
  - Linuxで`python3`がないか3.11未満: 終了コード127か1で、強制も検査も行われずに続く
  - Linuxで`git rev-parse --show-toplevel`が失敗する: PreToolUseは、Scriptを開けずにPythonが終了コード2で
    終わり、主Sessionを含めて、matcherに当たるTool呼び出しがすべて拒否される。SubagentStopは、Pythonを
    起動せずに続く
  - Windowsでどちらかが失敗する: 強制も検査も行われずに続く
- POSIXと食い違う記号と、許可リストにないpytest、sort、findのOptionは、Review Agentから使えない。
  `git show HEAD@{1}`のような参照はSHAで、単一引用符はWindowsでは二重引用符で、`sed -n '$p'`は`tail`で、
  Windowsのパスは`/`区切りで、`HEAD^`は`HEAD~1`で、`--format=%h`は`--oneline`で、findの`!`はWindowsでは
  `-not`で、正規表現の`$`や`\`は`-x`、`-w`、`[.]`、`-F`、`grep -E`で言い換える。拒否の理由にこの言い換えを
  示す。Shellの解釈に依存する判定の
  ため、ここで塞いだ種類以外の抜け道が見つかる可能性は残る
- Codexの`evidence-reviewer`は、許可外のShell（`curl`など）とMCPを拒否されるため、Web取得のToolが
  使えない環境では、開けない出典が増えて`unresolved`が多くなり得る（ADR 0017）
- 以前の`$git-guardrails-codex`のProjectの手順で、追跡していない`.codex/hooks.json`や`.codex/hooks/`を
  作った利用者は、この変更を取り込む前に、それを退避するか削除する
- Codexのmulti-agent v2の`followup_task`と`send_message`はmatcherに含めていない。読み取り専用の
  Agentが、書き込める別のAgentへ作業を頼めるかは確かめていない
- 主会話のモデルを変えても、Review Agentのモデルは変わらない。モデルの提供終了や改名の際は、
  TOMLの`model`と`CLAUDE_AGENT_MODELS`を同じ変更で更新する
- SubagentStop Hookは、結果が正しければトークンを使わない。欠けていた場合だけ、書き直しの分の
  トークンを使う。`SubagentHandback`で返した報告を書き直させたとき、主Sessionへ報告が2回届くかと、
  SubagentStopの時点で記録に`SubagentHandback`が書き込み済みかは確かめていない。`## Must`のような
  見出しの表記を変える場合は、Hook、指示、テストをそろえる
- `maxTurns`に達したレビューは、報告を返さずに止まることがある。大きな差分で上限に達することが
  続く場合は、過去の実行のターン数を数え直して上限を見直す
