# AIハーネス変更のチェックリスト

## Repository固有Skillを追加・変更する

- [ ] `SKILL.md`のFrontmatterは`name`と`description`だけで、`name`はDirectory名と一致する
- [ ] `description`と本文は日本語で、使用する場面と使用しない場面を含む
- [ ] `agents/openai.yaml`に日本語の`display_name`、`short_description`、`$<name>`を含む
      `default_prompt`がある
- [ ] Claude Code専用の起動設定（`effort`、`disallowed-tools`、`context`など）は正本へ書かず、
      `tools/sync_agent_config.py`の`CLAUDE_SKILL_SETTINGS`へ加える
- [ ] 利用者の明示時だけ起動するSkillは`policy.allow_implicit_invocation: false`を設定し、
      `EXPLICIT_ONLY_PROJECT_SKILLS`へ加える
- [ ] `EXPECTED_PROJECT_SKILLS`へ加える
- [ ] 詳細な知識は`references/`、決定的な処理は`scripts/`または`tools/`へ分ける
- [ ] `$choose-skill`の作業経路と`DEVELOPMENT.md`の共有スキル一覧を更新する

## 外部Skillを導入・除外する

- [ ] 導入時は`skills-lock.json`へ記録され、本文に秘密情報や危険なコマンドがないことを読んで確認する
- [ ] Python Repositoryで使わないエコシステム向けSkillを導入しない
- [ ] Repository固有化する場合は`skills-lock.json`から除外し、上の固有Skillの項目を満たす
- [ ] 削除する場合は`skills-lock.json`の項目とDirectoryを削除し、除外を確認するテストを加える

## Review Agentを変更する

- [ ] TOMLの`sandbox_mode`は`read-only`、`model_reasoning_effort`は`high`
- [ ] コードレビュー用のAgentは、指示に`Must`、`Should`、`Nice`の3段階を含む
- [ ] 生成される`.claude/agents/`が編集Toolを持たない。既定と異なるToolは
      `tools/sync_agent_config.py`の`CLAUDE_AGENT_TOOLS`で指定する
- [ ] Bashを持つ読み取り専用Agentが必要とする確認コマンドを、
      `tools/hooks/enforce_read_only_agent.py`の許可リストと`tests/test_agent_hooks.py`へ反映する
- [ ] 読み取り専用Agentの`tools`へ書き込み得るToolを加える場合は、`.claude/settings.json`の
      `enforce_read_only_agent.py`のmatcherにも加える

## Agent Hookを変更する

- [ ] Scriptは`tools/hooks/`に置き、標準ライブラリだけで動作する
- [ ] 標準入力はバイト列からUTF-8で読み、JSONはASCIIエスケープで出力する
- [ ] `main`の最初に標準出力と標準エラーをUTF-8へ再設定する
- [ ] `.claude/settings.json`ではexec形式で`python`と`${CLAUDE_PROJECT_DIR}`を使う
- [ ] 安全策のHookは解析できない入力を拒否し、補助的なHookは失敗しても作業を止めない
- [ ] `tests/test_agent_hooks.py`に許可、拒否、失敗時の判定を加える

## Codex専用Skillを扱う

- [ ] `tools/sync_agent_config.py`の`CODEX_ONLY_SKILLS`とテストの`CODEX_ONLY_SKILLS`を一致させる
- [ ] Codex専用Skillの本文に`.claude`のパスを書かない

## 仕上げ

- [ ] `python tools/sync_agent_config.py`を実行し、正本と生成物を同じ変更に含める
- [ ] 方針を変える場合はADRと`docs/adr/README.md`の索引を更新する
- [ ] `python tools/check.py`が成功する
