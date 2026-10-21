---
name: git-guardrails-codex
description: CodexのPreToolUse Hookを設定し、pushや作業内容を失うGitコマンドを実行前に拒否する。Git操作の安全策を追加または変更するときに使用する。
---

# CodexへGit保護ルールを設定する

Codexの`PreToolUse` HookでShellコマンドを検査し、次のGit操作を実行前に拒否する。

- `git push`
- `git reset --hard`
- `git clean -f`または`git clean -fd`
- `git branch -D`
- `git checkout .`
- `git restore .`
- `git worktree remove --force`または`git worktree remove -f`

このHookは補助的な安全策である。CodexのSandbox、Approval、RepositoryのBranch Protectionも
併用する。

## 1. 適用範囲を決める

利用者へ、現在のProjectだけに設定するか、すべてのProjectへ設定するか確認する。

- Project: `.codex/hooks.json`と`.codex/hooks/block_dangerous_git.py`
- User: `~/.codex/hooks.json`と`~/.codex/hooks/block_dangerous_git.py`

## 2. Scriptを配置する

Repositoryで共有する`tools/hooks/block_dangerous_git.py`を対象の`hooks`Directoryへコピーする。
このScriptはClaude CodeのProject Hookからも使用するため、保護対象の変更は正本である
`tools/hooks/`側で行う。既存ファイルを置き換える場合は、差分を提示して利用者の承認を得る。

## 3. Hookを追加する

既存の`hooks.json`がある場合は、他のHookを保ったまま`hooks.PreToolUse`へ追加する。
Project設定の例は次のとおり。

```json
{
  "description": "RepositoryのGit保護ルール",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .codex/hooks/block_dangerous_git.py",
            "commandWindows": "python .codex\\hooks\\block_dangerous_git.py",
            "statusMessage": "Gitコマンドの安全性を確認しています"
          }
        ]
      }
    ]
  }
}
```

User設定では、`command`と`commandWindows`へScriptの解決済み絶対パスを設定する。Homeを示す
未解決の環境変数を設定ファイルへ書き込まない。

## 4. 動作を検証する

危険なコマンドでは、標準出力へ`permissionDecision: deny`を含むJSONが返ることを確認する。
安全なコマンドでは、終了コード`0`かつ標準出力が空になることを確認する。

```text
{"hook_event_name":"PreToolUse","tool_input":{"command":"git push origin main"}}
{"hook_event_name":"PreToolUse","tool_input":{"command":"git status"}}
```

設定後はCodexの`/hooks`で新しいHookの内容を確認し、信頼する。保護対象を変更する場合はScriptの
テストも同時に更新する。
