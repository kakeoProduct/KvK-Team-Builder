# ADR 0017: Claude Code専用のSkill設定と、調査結果の独立検証・条件付き保存

- 状態: 採用
- 日付: 2026-10-17

## 背景

Opus 5.5のリリース（2026-09-22）以降に公開されたHarness設計の事例を、ADR 0015の適用後の
Skill群と再度照合した。対象は2026-10-06の「Make Opus 5.5 Finish Long Tasks」と、その周辺の投稿である。
その結果、次の不足が残っていた。

- `$review-kvk-change`の読み取り専用は文章だけで守られていた。Skill単位のeffortも指定して
  いなかった。Claude CodeのSkillは`disallowed-tools`、`effort`、`context`をFrontmatterで
  指定できるが、Codexとの共通の正本には書けない
- `$research`は同じSubagentが調査と判定を兼ねていた。主Agentが結論を左右する主張だけを
  再確認していたため、保存された文章そのものを独立に検証する工程がなかった
- `$research`はRepositoryへの保存を必須としていた。このため、調べるだけの依頼でも変更Sessionに
  なっていた。別Sessionが作業ツリーを使用中の場合は、worktreeへの移動まで必要になった

## 判断

- Claude Code専用の起動設定は正本のFrontmatterへ書かない。`tools/sync_agent_config.py`の
  `CLAUDE_SKILL_SETTINGS`から生成物へだけ加える。正本のFrontmatterは`name`と
  `description`に保つ
- `$review-kvk-change`には`disallowed-tools: Edit, Write, NotebookEdit`と`effort: high`を
  加える。この制限は次の利用者Messageで解除されるため、レビュー後の修正依頼を妨げない
- `$research`には`context: fork`を加え、Claude Codeでは独立したSubagentとして起動する。
  Subagentは会話履歴を見ないため、問い、保存の要否、保存先を`args`で渡す
- 読み取り専用の`evidence-reviewer`を`.codex/agents/`へ追加する。保存された下書きの各主張を
  出典と照合し、`verified`、`incorrect`、`unresolved`と訂正を返す。Claude Code向けには、
  `CLAUDE_AGENT_TOOLS`でWeb取得を与え、Shellを与えない。コードレビュー用ではないため、
  `Must`、`Should`、`Nice`の3段階は適用しない
- `$research`の下書きは常にGit管理外の`tmp/research/`へ書く。Repositoryへは、利用者が保存を
  求めた場合だけ置く。ADR 0015の「判定表を残す」という判断は下書きとして維持し、保存の
  必須化だけを改める

## 代替案

### Claude Code専用の項目を正本のFrontmatterへ書く

生成処理は単純になるが、CodexがSkillを読み込めるかを確認できていない。また、正本の
Frontmatterを`name`と`description`に限る構造テストとも矛盾する。

### Review Agent定義のTOMLへClaude Code用のTool一覧を書く

設定は1か所にまとまる。しかし、Codexが未知のキーを拒否するかどうかを確認できていない。
既存の`CODEX_ONLY_SKILLS`と同様に、同期Scriptの定数とする。

### 主Agentによる再確認を続ける

Agentの起動は増えない。しかし、調査した側の要約を前提にした再確認となり、保存された文章の
誤りを見落とし得る。

### 調査結果を常にRepositoryへ保存する

調査の来歴は必ず残る。しかし、相談だけの依頼でも変更Sessionと共有記憶の記録が必要になり、
並行Sessionの分離手順も起動する。

## 影響

- 調査1件ごとに証拠ReviewerのAgentが1回起動し、トークン消費が増える
- Claude Codeの`$research`はBackgroundで実行され、結果は完了通知で届く
- `tmp/research/`の下書きはGit管理外で、共有されない。残す必要がある調査は、利用者が保存を
  依頼する
- Codexでは`context`と`disallowed-tools`が効かない。このため、従来どおり本文の手順で
  Subagentへの委譲と読み取り専用を守る。Codexの読み取り専用sandboxでWeb取得ができない場合、
  証拠Reviewerは開けなかった出典を`unresolved`として返す
