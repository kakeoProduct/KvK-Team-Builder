# ADR 0014: Agent HookとSkill構成による作業手順の強制

- 状態: 採用
- 日付: 2026-10-15

## 背景

Opus 5.5以降のAgentは、Skillの手順を文字どおりに、止まらずに実行する傾向が強い。そのため、
次の問題が実害につながりやすくなった。

- Claude CodeにはHookがなく、危険なGit操作の拒否と共有記憶の開始・記録が、Agentが規約を
  覚えているかどうかに依存していた
- 外部から導入した`implement`が「現在のブランチへコミットする」「`/code-review`を使う」と
  指示し、利用者の明示を求める`AGENTS.md`と`$review-kvk-change`の方針と矛盾していた
- 生成結果の確認は「生成Markdownも確認する」という記述だけで、決まった手順がなかった
- Python Repositoryで使わないTypeScript／JavaScript向けSkillが、毎回Skill一覧を占有し、
  誤って選ばれる余地を残していた
- 共有記憶の昇格候補は仕組みがあるのに、検討を始めるきっかけがなかった

## 判断

- Git保護Scriptを`tools/hooks/block_dangerous_git.py`へ移し、CodexとClaude Codeで共有する。
  既定ではpushを含めて拒否する。Claude Codeでは`--ask-push`を指定し、通常のpushは利用者確認、
  強制pushと作業内容を失う操作は拒否とする。Hookの入出力はWindowsのコードページへ依存せず
  UTF-8で扱う
- `.claude/settings.json`へPreToolUse、SessionStart、Stopの各Hookを登録する。Windowsで
  シェルの変数展開へ依存しないよう、exec形式で`${CLAUDE_PROJECT_DIR}`を渡す
- 共有記憶のSessionStart Hookは、Claude Codeのsession_idで`start --keep-existing`を実行する。
  Stop Hookは`status --mark-reminded`で未記録の変更を調べ、1 Sessionに1回だけ停止を止める。
  どちらも失敗時は作業を止めない
- `implement`を外部管理から外してRepository固有Skillとし、完了条件、`tmp/progress/`による
  再開、`$review-kvk-change`、利用者の明示によるコミットを定める
- `tools/preview_output.py`で生成結果の自己チェック、警告、前回との差分を表示し、
  `$change-kvk-rules`と`$implement`から使用する
- `migrate-to-shoehorn`、`scaffold-exercises`、`setup-pre-commit`、`setup-ts-deep-modules`を
  削除する
- `finish`は既定タグ以外の同じタグを持つ記憶が3件以上になると`promotion_hints`を返す。
  昇格の判断は従来どおり利用者の承認を必要とする

## 代替案

### Stop Hookで毎回停止を止める

記録漏れは確実に防げるが、作業途中で利用者の判断を待つたびに不要な継続が発生する。
1 Sessionに1回の催促とし、最終的な判断はAgentと利用者に委ねる。

### Stop Hookで自動的に`finish`を実行する

依頼、結果、判断を機械的に埋めると、記憶の質が下がり誤った記録が残る。採用しない。

### 生成結果を正解ファイルと比較して合否を判定する

CP-SATは制限時間内の探索結果を返すため、ルールと無関係な差分で失敗し得る。合否は
自己チェックと品質ゲートで判断し、差分は確認材料として表示するにとどめる。

### `implement`を外部Skillのまま、ローカルで上書きする

`skills-lock.json`のHashと内容が一致しなくなり、再導入時に方針と矛盾する内容へ戻る。
Repository固有Skillとして管理する。

### 他エコシステム向けSkillを残し、暗黙起動だけを禁止する

誤起動は減るが、使わないSkillの保守と同期が残る。必要になった時点で再導入する。

## 影響

Claude Codeでは、信頼したWorkspaceでHookが自動的に動作する。`python`をPATHから実行できない
環境ではHookが動作しないため、開発ガイドに前提を記載する。共有記憶の開始状態は、
読み取りだけのSessionでもOSの一時Directoryへ保存される。Codexの共有記憶は従来どおり
Skillの手順で開始と記録を行う。削除したSkillを再び使う場合は、改めて導入を判断する。
