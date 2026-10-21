"""CodexとClaude CodeのPreToolUse入力を検査し、危険なGitコマンドを止める。

既定ではpushを含む対象操作をすべて拒否する。`--ask-push`を指定すると、通常の
pushだけを利用者確認へ回し、強制pushと作業内容を失う操作は引き続き拒否する。
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections.abc import Iterator
from typing import Any

COMMAND_SEPARATOR = re.compile(r"&&|\|\||[;|\r\n]")
GIT_OPTIONS_WITH_VALUE = {
    "-C",
    "-c",
    "--exec-path",
    "--git-dir",
    "--namespace",
    "--super-prefix",
    "--work-tree",
}
FORCE_PUSH_OPTIONS = {"--force", "--force-with-lease", "--force-if-includes"}
PUSH_OPERATION = "git push"


def _command_segments(command: str) -> Iterator[list[str]]:
    """Shellコマンドを分割し、解析できたToken列を返す。"""

    for segment in COMMAND_SEPARATOR.split(command):
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            continue
        if tokens:
            yield tokens


def _git_arguments(tokens: list[str]) -> list[str] | None:
    """Token列からGit実行部分の引数を返す。"""

    git_index = next(
        (
            index
            for index, token in enumerate(tokens)
            if token.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
            in {"git", "git.exe"}
        ),
        None,
    )
    if git_index is None:
        return None

    arguments = tokens[git_index + 1 :]
    index = 0
    while index < len(arguments) and arguments[index].startswith("-"):
        option = arguments[index]
        index += 1
        if option.split("=", 1)[0] in GIT_OPTIONS_WITH_VALUE and "=" not in option:
            index += 1
    return arguments[index:]


def _is_force_push(options: list[str]) -> bool:
    """pushの引数が強制更新を含むか判定する。"""

    return any(
        option.split("=", 1)[0] in FORCE_PUSH_OPTIONS
        or (option.startswith("-") and not option.startswith("--") and "f" in option)
        or (option.startswith("+") and len(option) > 1)
        for option in options
    )


def _blocked_operation(command: str) -> str | None:
    """拒否対象の操作名を返す。"""

    for tokens in _command_segments(command):
        arguments = _git_arguments(tokens)
        if not arguments:
            continue

        subcommand = arguments[0].lower()
        options = arguments[1:]
        if subcommand == "push":
            return "git push --force" if _is_force_push(options) else PUSH_OPERATION
        if subcommand == "reset" and "--hard" in options:
            return "git reset --hard"
        if subcommand == "clean" and any(
            option == "--force"
            or (
                option.startswith("-") and not option.startswith("--") and "f" in option
            )
            for option in options
        ):
            return "git clean -f"
        if subcommand == "branch" and "-D" in options:
            return "git branch -D"
        if subcommand in {"checkout", "restore"} and "." in options:
            return f"git {subcommand} ."
        if (
            subcommand == "worktree"
            and options[:1] == ["remove"]
            and any(option in {"--force", "-f"} for option in options[1:])
        ):
            return "git worktree remove --force"
    return None


def _decide(decision: str, reason: str) -> None:
    """AgentがTool呼び出しを拒否または確認できるJSONを出力する。"""

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    # 既定コードページへ依存しないよう、非ASCII文字をエスケープして出力する。
    print(json.dumps(output, ensure_ascii=True))


def _deny(reason: str) -> None:
    """Tool呼び出しを拒否する。"""

    _decide("deny", reason)


def _read_command(payload: Any) -> str | None:
    """Hook入力からShellコマンドを取得する。"""

    if not isinstance(payload, dict) or payload.get("hook_event_name") != "PreToolUse":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    return command if isinstance(command, str) else None


def _use_utf8_output() -> None:
    """Windows CIなど非UTF-8のConsoleでも日本語の出力で失敗しないようにする。"""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def create_argument_parser() -> argparse.ArgumentParser:
    """Hook Scriptの引数Parserを生成する。"""

    parser = argparse.ArgumentParser(description="危険なGitコマンドを止めます。")
    parser.add_argument(
        "--ask-push",
        action="store_true",
        help="通常のpushを拒否せず、利用者確認へ回す",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """標準入力のHook Payloadを検査する。"""

    _use_utf8_output()
    args = create_argument_parser().parse_args(argv)

    # Windowsの既定コードページへ依存せず、HookのJSONをUTF-8として読む。
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        _deny("Git保護ルールがHook入力を解析できなかったため拒否しました。")
        return 0

    command = _read_command(payload)
    if command is None:
        _deny("Git保護ルールがShellコマンドを確認できなかったため拒否しました。")
        return 0

    blocked_operation = _blocked_operation(command)
    if blocked_operation == PUSH_OPERATION and args.ask_push:
        _decide(
            "ask",
            "Git保護ルールにより、git pushの実行前に利用者の確認を求めます。",
        )
    elif blocked_operation is not None:
        _deny(f"Git保護ルールにより{blocked_operation}を拒否しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
