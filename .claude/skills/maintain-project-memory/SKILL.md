---
name: maintain-project-memory
description: 機能実装やリポジトリ変更を行うセッションについて、開始状態との差分を判定し、共有記憶、索引、昇格候補を安全に管理する。変更作業の開始・完了時、利用者から記憶を依頼されたとき、または過去の記憶をAGENTS.md、Skill、ADR、正本文書、Script、レビューAgentへ昇格するときに使用する。調査、相談、説明、読み取り専用レビューだけのセッションでは、明示的な記録依頼がない限り共有記憶を作成しない。
---

<!-- このファイルは tools/sync_agent_config.py が.agents/skills/maintain-project-memory/SKILL.mdから生成します。直接編集せず、正本を変更してから同期してください。 -->

# プロジェクト記憶を管理する

変更セッションの要点をGit管理の共有記憶へ残し、反復する知識を適切な正本へ昇格する。
CodexやClaude CodeのローカルMemoryを補助として扱い、必須規約やプロダクト契約の正本にしない。

## 変更セッションを開始する

機能実装またはリポジトリ変更を依頼されたら、編集前に次を実行する。

```text
python .agents/skills/maintain-project-memory/scripts/session_memory.py start
```

JSON出力の`session_id`を保持する。開始時点から存在する利用者の差分を上書きせず、記憶の
対象にも含めない。調査、相談、説明、読み取り専用レビューだけなら実行しない。

出力の`other_active_sessions`は、同じ作業ツリーで最後の操作から3時間以内の別Sessionを示す。
1件以上なら`use_separate_worktree`が`true`になる。変更作業では`$implement`の手順でSession用
worktreeへ移り、元の作業ツリーの開始状態を次で破棄してから、移動先で`start`をやり直す。
`finish`で代用すると、別Sessionの差分を自分の記憶として記録してしまう。

```text
python .agents/skills/maintain-project-memory/scripts/session_memory.py discard --session-id <session_id>
```

Claude Codeでは`.claude/settings.json`のSessionStart Hookが、Claude Codeのsession_idで
`start --keep-existing`を自動実行し、そのsession_idをContextへ渡す。別Sessionが使用中なら、
worktreeへ移る指示もContextへ加える。この場合はstartを
再実行せず、渡されたsession_idで`finish`する。Stop Hookは未記録の変更が残ると1 Sessionに
1回だけ停止を止めて`finish`を促す。作業途中で利用者の判断を待つ場合は、その旨を伝えて
停止してよい。未記録の変更は次で確認できる。

```text
python .agents/skills/maintain-project-memory/scripts/session_memory.py status --session-id <session_id>
```

## 変更セッションを記録する

実装と対象チェックを終えたら、最終報告の前に`finish`を実行する。

```text
python .agents/skills/maintain-project-memory/scripts/session_memory.py finish \
  --session-id <session_id> \
  --title "変更の短い題名" \
  --request "利用者の依頼の要約" \
  --outcome "実装結果" \
  --decision "重要な判断" \
  --verification "実行コマンド: 結果" \
  --remaining "未完了なし" \
  --tag ai-harness
```

Windows PowerShellでは継続記号へ依存せず、同じ引数を1行で渡す。スクリプトは開始時と
終了時のGit状態を比較し、次のいずれかに該当するときだけ記憶を作る。

- セッションによる有効なリポジトリ差分が残った
- セッション中のコミットに有効なリポジトリ差分が含まれる
- 利用者の明示的な記録依頼により`--force`を指定した

記憶自身、既存の利用者差分、Gitの除外対象、一時生成物だけの変化は判定から外す。変更を
すべて取り消して成果が残らなかった場合も、`--force`がなければ記録しない。

会話全文、秘密情報、個人情報、長いログは保存しない。依頼、結果、変更パス、判断、検証、
未完了事項、正本への参照だけを簡潔に残す。必要なら`--decision`、`--verification`、
`--remaining`、`--tag`を複数指定する。

## 記憶を検索する

変更作業の開始時に`docs/project-memory/INDEX.md`を読み、タグと関連パスが近い記憶を最大3件
選ぶ。過去の記憶だけで現在の事実を断定せず、README、Architecture、ADR、設定、テスト、
現在のコードで再確認する。`promoted`または`superseded`の候補は本文を再適用せず、昇格先を
正本として読む。

## 昇格候補を管理する

`finish`の出力に`promotion_hints`がある場合は、既定タグ以外の同じタグを持つ記憶が3件以上
あることを示す。該当記憶を読み、同じ手順、失敗、判断が本当に反復しているときだけ、
昇格候補の作成を利用者へ提案する。ヒントだけを根拠に候補を作らない。

同じ手順、失敗、判断が独立した複数セッションで現れたら、
`assets/promotion-candidate-template.md`を基に`docs/project-memory/candidates/`へ候補を作る。
利用者が明示的に昇格を依頼した場合は、1件の根拠でも候補にできる。

内容に応じて昇格先を選ぶ。

- 毎回必ず守る短い規約: `AGENTS.md`
- トリガーを持つ複数手順の作業: `.agents/skills/`
- 決定的に繰り返す処理: Skillの`scripts/`または`tools/`
- Skill実行時だけ必要な詳細: Skillの`references/`
- 利用者向け契約: `README.md`とテスト
- 重要な設計判断: `docs/adr/`
- ドメイン用語または不変条件: `docs/domain-model.md`
- 独立した専門レビュー責務: `.codex/agents/`（Claude Code向けは同期Scriptで生成する）
- 複数Repositoryへ配布する一式: Pluginを別変更として検討する

候補の状態を`observed -> candidate -> ready -> promoted`で進める。却下は`rejected`、古くなった
候補は`superseded`にする。反復回数だけで自動昇格せず、利用者の承認または昇格を含む明示的な
依頼を得てから対象ファイルを変更する。

Skillへ昇格するときは既存Skillとの重複を確認し、`SKILL.md`を簡潔に保つ。詳細知識は
`references/`、決定的な処理は`scripts/`へ分け、Skill Creatorの`quick_validate.py`と
`python tools/check.py`を実行する。

昇格後も根拠となったセッション記憶は削除しない。候補を`promoted`へ更新し、`promoted_to`へ
正本のパスを設定する。以後、記憶は来歴としてだけ利用する。

## 整合性を検証する

手作業で記憶や候補を変更した場合は索引を再生成する。

```text
python .agents/skills/maintain-project-memory/scripts/session_memory.py rebuild-index
python .agents/skills/maintain-project-memory/scripts/session_memory.py validate
```

記憶を含む変更の完了前に`python tools/check.py`も実行する。記憶作成後に検証結果だけを更新した
場合は、少なくとも`validate`と`tests/test_ai_harness.py`を再実行し、最終報告で実行順を明示する。
