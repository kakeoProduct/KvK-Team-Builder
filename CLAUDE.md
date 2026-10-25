# Claude Code向け開発ルール

開発ルールの正本は`AGENTS.md`です。CodexとClaude Codeは同じ規約に従います。

@AGENTS.md

## Claude Codeでの読み替え

- `AGENTS.md`の`$skill-name`は、Claude Codeでは`/skill-name`またはSkill Toolで呼び出す
- Skillの正本は`.agents/skills/`、Review Agentの正本は`.codex/agents/`とする
- `.claude/skills/`と`.claude/agents/`は`python tools/sync_agent_config.py`の生成物であり、
  直接編集しない。正本を変更したら同期Scriptを実行し、両方を同じ変更に含める
- Codexが解釈しないSkillの起動設定は、同期Scriptが生成物のFrontmatterへだけ加える。
  `$review-kvk-change`は`disallowed-tools`で編集Toolを外し、`effort: high`で動く。この制限は
  次の利用者Messageで解除される。`$research`は`context: fork`でSubagentとして起動するため、
  Skill Toolの`args`へ問い、保存の要否、保存先と、起動の前に主Sessionが確かめた読み取り専用の強制の
  結果（SessionStart HookのContextが届いていれば動いている）を渡す。利用者が`/research`で直接起動した
  場合は結果が渡らないため、独立検証をせず、そのことを報告に書く。独立検証が要る調査は主Sessionに
  依頼する（ADR 0031）
- `$review-kvk-change`の4つのReview Agentは、`.claude/agents/`の同名Subagentとして
  並列に起動する。Subagentは編集Toolを持たない
- `codex-handoff`と`git-guardrails-codex`はCodex専用のため、Claude Codeへ同期しない
- `.claude/settings.json`のHookがGit保護と共有記憶の開始・記録漏れ確認を行う。
  SessionStart Hookがsession_idをContextへ渡した場合は、`$maintain-project-memory`の
  startを再実行せず、そのsession_idで`finish`する。ただし`$implement`の開始手順2で分岐元を移った
  場合は、同手順に従って同じsession_idで`discard`と`start`をやり直す
- `$implement`で決めた完了条件は`/goal`へ渡し、会話に表示した検証結果で判定させる。
  停止条件も含める。判定はモデルが会話を読んで行うため、品質ゲートの実行そのものの代わりにしない
- `$implement`でSession用worktreeへ移るときは、`git worktree add`の代わりにEnterWorktree Toolを
  使う。作成先は`.claude/worktrees/`で、移動後のHookは`cwd`からそのworktreeの開始状態を使う。
  EnterWorktreeは`origin/<既定branch>`から作り、既存の複製の`origin/HEAD`はGitHubの既定branchの変更に
  追従しない。このため移動後は常に、`$implement`の「Session用worktreeへ移る」の手順2で選んだコミット
  （元が`main`か`dev`なら`git fetch origin dev`の後の`origin/dev`、それ以外は元のHEAD）と
  `git rev-parse HEAD`を比べる。一致せず、まだ何も変更していなければ
  `git switch --no-track -C <現在のbranch名> <選んだコミット>`で付け替える。変更があるか、分岐元が
  `origin/dev`のときにfetchが失敗するか`origin/dev`がなければ、利用者へ確認する。付け替えの前に開始状態を保存して
  いれば、同じsession_idで`discard`と`start`をやり直す（ADR 0027）
- Subagentの`permissionMode: plan`は、親Sessionが`auto`、`acceptEdits`、`bypassPermissions`の
  とき無視される。このため`tools/hooks/enforce_read_only_agent.py`を`.claude/settings.json`へ
  書き込み得るToolだけを対象に登録し、`.codex/agents/`で`sandbox_mode = "read-only"`のAgentには
  許可した確認コマンドだけを通す。Subagent定義のFrontmatterへ書いたHookは、Agentファイルのある
  フォルダそのものを信頼したときだけ動き、`claude -p`では動かないため使わない（ADR 0031）。
  Hookの追加と変更は、Claude Codeの新しいSessionから有効になる。SessionStart HookのContextが届いて
  いれば、Project Hookは動いている
- Claude Code用の`model`の値と`maxTurns`は、Codexと値が異なるか同等の設定がないため、同期Scriptが
  生成物のFrontmatterへだけ加える。重い担当（要件、アーキテクチャ、証拠）は`opus`、ほかは`sonnet`とし、
  主会話のモデルを継承させない。`maxTurns`はドメイン、テスト、要件の担当が40、`kvk-architecture-reviewer`と`evidence-reviewer`が60
  （ADR 0031）
- `.claude/settings.json`の`permissions.deny`は、生成物の直接編集と`.env`の読み取りを拒否する。
  Pythonなど編集Tool以外からの書き込みは対象外のため、同期Scriptは従来どおり実行できる
- `CLAUDE.md`にはClaude Code固有の読み替えだけを書き、共通の規約は`AGENTS.md`へ書く
