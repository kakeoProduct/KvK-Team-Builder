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

このRepositoryでは、追跡する`.codex/hooks.json`に`tools/hooks/block_dangerous_git.py`を登録済み
である（ADR 0031）。Projectの範囲では追加の設定をせず、`/hooks`でこのHookを信頼済みかを確かめる。
`.codex/hooks.json`へScriptのコピーや相対パスのHookを追記しない。保護対象を変える場合は、正本の
`tools/hooks/`とテストを変更する。

すべてのProjectへ設定するかを利用者へ確認し、希望した場合だけ次のUser設定を作る。

- User: `~/.codex/hooks.json`と`~/.codex/hooks/block_dangerous_git.py`

## 2. Scriptを配置する

Repositoryで共有する`tools/hooks/block_dangerous_git.py`を`~/.codex/hooks/`へコピーする。
このScriptはClaude CodeのProject Hookからも使用するため、保護対象の変更は正本である
`tools/hooks/`側で行う。既存ファイルを置き換える場合は、差分を提示して利用者の承認を得る。

## 3. Hookを追加する

既存の`~/.codex/hooks.json`がある場合は、他のHookを保ったまま`hooks.PreToolUse`へ追加する。
User設定の例は次のとおり。`<Scriptの絶対パス>`は、コピーしたScriptの解決済み絶対パスに置き換える。

```json
{
  "description": "Git保護ルール",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"<Scriptの絶対パス>\"",
            "commandWindows": "python \"<Scriptの絶対パス>\"",
            "statusMessage": "Gitコマンドの安全性を確認しています"
          }
        ]
      }
    ]
  }
}
```

Homeを示す未解決の環境変数を設定ファイルへ書き込まない。

## 4. 動作を検証する

危険なコマンドでは、標準出力へ`permissionDecision: deny`を含むJSONが返ることを確認する。
安全なコマンドでは、終了コード`0`かつ標準出力が空になることを確認する。

```text
{"hook_event_name":"PreToolUse","tool_input":{"command":"git push origin main"}}
{"hook_event_name":"PreToolUse","tool_input":{"command":"git status"}}
```

設定後はCodexの`/hooks`で新しいHookの内容を確認し、信頼する。保護対象を変更する場合はScriptの
テストも同時に更新する。
