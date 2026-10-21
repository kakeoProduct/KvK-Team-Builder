# プロジェクト共有記憶

このDirectoryは、機能実装またはRepository変更が発生したSessionの要点と、複数Sessionで
繰り返された知識の昇格候補を、人間とAIが共有できるMarkdownとして管理します。

CodexやClaude CodeのLocal Memoryは過去の文脈を思い出すための補助です。必須規約、利用者向け契約、
Architecture、運用設定、実行可能な仕様は、それぞれ`AGENTS.md`、`README.md`、
`docs/architecture.md`、`src/kvk_team/team_building/adapters/persistence/team_master.json`、`tests/`を正本とします。

## Directory構成

```text
docs/project-memory/
├── README.md
├── INDEX.md
├── sessions/<year>/<timestamp>-<slug>.md
└── candidates/<candidate-id>.md
```

- `sessions/`: 変更Sessionの依頼、結果、変更パス、判断、検証、未完了事項を追記型で残す。
  例外は、ADR 0026で伏せた語と、それを含む識別子の表記の書き換えと、書き換えたことを示す注記だけとする。当時の表記は
  アーカイブした旧Repositoryの履歴にある
- `candidates/`: 複数Sessionの根拠をまとめ、Skillなどへの昇格状態を管理する
- `INDEX.md`: Scriptが生成する検索用索引。手作業で編集しない

会話全文、秘密情報、個人情報、長いTool出力、一時的な試行錯誤は保存しません。

## 記憶するSession

次のいずれかを満たすSessionを記録します。

- 新機能、バグ修正、Refactoringなどを実装した
- Code、設定、Test、文書を変更した
- 開始後のCommitへ有効なRepository変更を含めた
- 利用者が明示的に記録を依頼した

調査、相談、説明、読み取り専用ReviewだけのSession、Git除外対象だけが変わったSession、
すべての変更を取り消して成果が残らなかったSessionは、明示的な依頼がなければ記録しません。

変更前の利用者差分を記憶へ混ぜないため、`$maintain-project-memory`はSession開始時のHEADと
作業ツリー内容をOSの一時Directoryへ保存し、終了時との差だけを判定します。一時状態はGitへ
追加せず、記憶作成または記録不要判定の成功後に削除します。

## 検索と適用

新しい変更Sessionでは最初に`INDEX.md`を読み、タグまたは関連パスが近い記憶を最大3件だけ
選びます。記憶から得た内容は、現在の正本と実装で再確認してから利用します。

`superseded`のSessionや、`promoted`、`rejected`、`superseded`の昇格候補を古い手順として
再適用しません。`promoted`では`promoted_to`が示す昇格先を読みます。

## 知識の昇格

昇格候補は次のLifecycleで管理します。

```text
observed -> candidate -> ready -> promoted
                         |-> rejected
                         |-> superseded
```

独立した複数Sessionで同じ手順、失敗、判断が現れた場合、または利用者が明示的に昇格を
依頼した場合に候補を作成します。反復回数だけで自動昇格せず、利用者の承認または昇格を含む
明示的な実装依頼を得てから昇格先を変更します。

| 内容 | 昇格先 |
|---|---|
| 毎回必ず守る短い規約 | `AGENTS.md` |
| Triggerを持つ複数手順の作業 | `.agents/skills/` |
| 決定的に繰り返す処理 | Skillの`scripts/`または`tools/` |
| Skill実行時だけ必要な詳細知識 | Skillの`references/` |
| 利用者向け契約 | `README.md`とTest |
| 重要な設計判断 | `docs/adr/` |
| Domain用語または不変条件 | `docs/domain-model.md` |
| 独立した専門Review責務 | `.codex/agents/`（`.claude/agents/`は生成物） |
| 複数Repositoryへ配布する一式 | Plugin |

昇格後も根拠のSessionは削除しません。候補を`promoted`にし、`promoted_to`へ正本の相対パスを
設定します。以後、候補は来歴としてだけ参照します。

## 操作

変更Sessionの開始:

```text
python .agents/skills/maintain-project-memory/scripts/session_memory.py start
```

終了時の記録判定と作成:

```text
python .agents/skills/maintain-project-memory/scripts/session_memory.py finish --help
```

索引の再生成と検証:

```text
python .agents/skills/maintain-project-memory/scripts/session_memory.py rebuild-index
python .agents/skills/maintain-project-memory/scripts/session_memory.py validate
```

詳細な手順と昇格候補Templateは`$maintain-project-memory`を参照してください。
