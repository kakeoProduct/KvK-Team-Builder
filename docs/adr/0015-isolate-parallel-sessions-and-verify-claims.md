# ADR 0015: 並行Sessionのworktree分離と、検証可能な完了・調査・レビュー

- 状態: 提案中
- 日付: 2026-10-15

## 背景

Opus 5.5向けのHarness設計の公開事例（2026-10-06の「Make Opus 5.5 Finish Long Tasks」など）を
このRepositoryのSkillと照合した。プロジェクト記憶、Skill、PreToolUse Hook、読み取り専用の
Reviewer、進捗ファイルは採用済みだった。一方で次の不足が見つかった。

- `.claude/skills/`と`.claude/agents/`を直接編集しない規約が、文章だけで守られていた
- `.env`を読まない、TOKENを表示しないという方針に、Toolの権限による裏付けがなかった
- 同じ作業ツリーを複数Sessionが同時に編集すると、差分、品質ゲート、共有記憶の判定が混ざった
- `$implement`の完了条件が、会話上の証拠で判定できる形になっていなかった
- 外部Skillの`research`は英語で、主張ごとの判定、出典、確認日を残す手順がなかった
- `$review-kvk-change`は確かめきれない懸念を捨てるため、人間が追加調査を判断できなかった

## 判断

- `.claude/settings.json`へ`permissions.deny`を追加し、`Edit(.claude/skills/**)`、
  `Edit(.claude/agents/**)`、`Read(.env)`、`Read(.env.*)`を拒否する。実行系の規則は加えず、
  同期Scriptと品質ゲートの動作を変えない
- 共有記憶の開始状態へ`last_seen_at`を持たせる。`start`と、Stop Hookが毎Turn呼ぶ`status`で
  更新する。`start`は、同じ作業ツリーで最後の操作から3時間以内の別Sessionを
  `other_active_sessions`として返し、1件以上なら`use_separate_worktree`を`true`にする
- 別Sessionが使用中のときだけ、`$implement`はSession専用のworktreeとbranchへ移る。Codexは
  `.worktrees/`へ`git worktree add`で作り、Claude CodeはEnterWorktree Toolで
  `.claude/worktrees/`へ作る。どちらもGitの除外対象とする。元の開始状態は新しい`discard`で
  破棄し、移動先で`start`をやり直す
- 共有記憶HookはPayloadの`cwd`がRepository内のSession用worktreeを指す場合だけ、その
  worktreeの共有記憶Scriptを使う。それ以外の`cwd`は信用せず、元の作業ツリーとして扱う
- 共有記憶Hookは、実行中のOSに合うvenvのPythonだけを使う。Windowsと共有するWorkspaceでは
  Linuxから`.venv/Scripts/python.exe`が見え、これを起動してHookが常に失敗していたため
- Git保護Hookは、未コミットの変更を失う`git worktree remove --force`を拒否する
- `$implement`の完了条件を、会話に表示した検証結果で判定できる形で書き、停止条件を含める。
  Claude Codeではこの条件を`/goal`へ渡す
- `research`を外部管理から外し、日本語のRepository固有Skillとする。主張ごとに`verified`、
  `incorrect`、`unresolved`を付け、出典URL、確認日、発表日と提供開始日の区別を残す
- `$review-kvk-change`とReview Agentは、確かめきれない具体的な疑いを「未確定の懸念」として
  不足証拠と一緒に分けて返す。未確定の懸念は承認判定に含めない

## 代替案

### 常にworktreeで作業する

並行作業の衝突はなくなるが、単独Sessionでも毎回branchと作業Directoryが増え、利用者が変更を
確認する場所が分散する。使用中の場合だけ分離する。

### Lockファイルで作業ツリーを排他する

確実に排他できるが、異常終了したSessionのLockが残ると、利用者が手作業で解除するまで作業が
止まる。時間経過で失効する使用中の判定とする。

### 未コミットの差分の有無で使用中を判定する

利用者自身の作業途中の差分と、別Sessionの差分を区別できない。Session単位の開始状態で判定する。

### `.claude/rules/`でAGENTS.mdを分割する

Claude Codeの文脈消費は減るが、Codexと共有する`AGENTS.md`の正本が二重になる。採用しない。

### `research`をローカルで上書きする

`skills-lock.json`のHashと一致しなくなり、再導入時に方針と矛盾する内容へ戻る。ADR 0014と同様に
Repository固有Skillとする。

## 影響

- 並行Sessionの変更が別のbranchへ分かれる。統合とworktreeの削除は利用者が明示した場合だけ行う
- 3時間以内に終了した読み取り専用Sessionも使用中に数えるため、不要なworktreeが作られ得る。
  安全側の誤判定として受け入れる
- Codexには毎Turnの`status`呼び出しがないため、長いCodex Sessionは開始から3時間で使用中の
  判定から外れる
- `permissions.deny`はClaude Codeの編集・読み取りToolだけを対象とし、Shellからの操作は
  防がない。Git保護Hookとsandboxを併用する
