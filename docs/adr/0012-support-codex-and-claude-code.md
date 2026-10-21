# ADR 0012: CodexとClaude Codeの両対応

- 状態: 提案中
- 日付: 2026-10-15

## 背景

開発規約、Skill、Review Agentは`AGENTS.md`、`.agents/skills/`、`.codex/agents/`として
Codex向けに整備されている。Claude Codeは`CLAUDE.md`、`.claude/skills/`、`.claude/agents/`
を読み込むため、そのままでは規約もSkillもReview Agentも認識しない。どちらのAgentで開発を
続けても同じ規約、手順、レビュー観点が適用される必要がある。

## 判断

- 正本は従来どおり`AGENTS.md`、`.agents/skills/`、`.codex/agents/`とする
- `CLAUDE.md`は`@AGENTS.md`を取り込み、Claude Code固有の読み替えだけを記述する
- `tools/sync_agent_config.py`が正本からClaude Code向けのSkillとSubagentを生成する
  - SKILL.mdには生成元の注記を加え、Codexで暗黙起動を禁止したSkillには
    `disable-model-invocation: true`を付与する
  - Codex UI専用の`agents/openai.yaml`と、Codex専用Skill（`codex-handoff`、
    `git-guardrails-codex`）は複製しない
  - Review AgentはTOMLの説明と指示を移し、編集Toolを持たない構成と`permissionMode: plan`を
    指定する
- 生成物はGit管理し、`python tools/check.py`が同期のずれを検出して失敗させる。
  `--fix`は同期も実行する
- Dev ContainerへClaude CodeのVS Code拡張機能`anthropic.claude-code`を追加する
- `.claude/settings.local.json`など利用者ローカルの設定はGit管理しない

## 代替案

### Symbolic Linkで`.claude/skills`を`.agents/skills`へ向ける

複製は不要になるが、Windowsでは`core.symlinks`や開発者モードに依存し、cloneした環境に
よってはリンクが通常ファイルとして展開される。Windowsを対象環境とする開発ルールに反する
ため採用しない。

### 生成物をGit管理せず、Session開始Hookで生成する

Repositoryの重複は減るが、clone直後にSkillが存在せず、HookとSkill読込の順序に依存する。
確実性を優先して採用しない。

### Claude Code向けを正本にする

直前にCodex向けへ移行した経緯があり、Codex固有のメタデータ（`openai.yaml`、TOML）を
失わずに逆変換する利点がないため採用しない。

## 影響

Skillを追加または変更したときは同期Scriptの実行が必要になり、差分には正本と生成物の両方が
含まれる。品質ゲートが同期漏れを検出するため、片方だけが更新された状態はCIで失敗する。
`permissionMode`とTool制限は親Sessionの権限で上書きされ得るため、ADR 0002と同様に設定だけを
読み取り専用の保証として扱わず、Review Agentの指示でも編集を禁止する。
