"""読み取り専用のReview AgentのTool呼び出しを、権限モードにかかわらず制限する。

Claude Codeでは親Sessionが`auto`、`acceptEdits`、`bypassPermissions`のとき、Subagentの
`permissionMode: plan`が無視される。PreToolUse Hookの拒否は権限モードより先に評価される
ため、`.claude/settings.json`へ登録して`plan`相当の制限を強制する。Subagent定義の
Frontmatterへ書いたHookは、この環境では発火しなかった。

Hook入力の`agent_type`が、正本の`.codex/agents/`で`sandbox_mode = "read-only"`と宣言した
Agentのときだけ制限する。主Sessionと他のAgentのTool呼び出しは判定せず通す。

`.claude/settings.json`のmatcherは、書き込み得るTool（Bash、PowerShell、Monitor、編集Tool、
Agent、MCP）だけをこのHookへ渡す。読み取りToolと内部Toolでは起動しないため、Claude Codeが
内部Toolを増やしても結果の返却を妨げない。制限対象のAgentでは、届いたToolのうちBashの
許可した確認コマンドだけを通し、それ以外と解析できない入力は拒否する。
"""

from __future__ import annotations

import json
import re
import shlex
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_DEFINITION_DIRECTORY = PROJECT_ROOT / ".codex" / "agents"

COMMAND_SEPARATORS = frozenset({"&&", "||", "|", ";"})
REDIRECT_OPERATORS = frozenset({">", ">>", ">&"})
# 出力先を持たず、ファイルを変更しないコマンド。
READ_ONLY_COMMANDS = frozenset(
    {
        "basename",
        "cat",
        "cd",
        "diff",
        "dirname",
        "du",
        "echo",
        "egrep",
        "fgrep",
        "grep",
        "head",
        "ls",
        "nl",
        "pwd",
        "realpath",
        "stat",
        "tail",
        "true",
        "wc",
        "which",
    }
)
READ_ONLY_GIT_SUBCOMMANDS = frozenset(
    {
        "blame",
        "cat-file",
        "describe",
        "diff",
        "for-each-ref",
        "grep",
        "log",
        "ls-files",
        "ls-tree",
        "merge-base",
        "name-rev",
        "rev-list",
        "rev-parse",
        "shortlog",
        "show",
        "show-ref",
        "status",
    }
)
# 値を取るGitの大域Option。`-c`などの設定変更はPagerやHookを実行し得るため含めない。
GIT_GLOBAL_OPTIONS_WITH_VALUE = frozenset({"-C", "--git-dir", "--work-tree"})
GIT_GLOBAL_FLAGS = frozenset({"--no-pager", "-P"})
GIT_BRANCH_LIST_OPTIONS = frozenset(
    {"-a", "--all", "-r", "--remotes", "-l", "--list", "-v", "-vv", "--show-current"}
)
GIT_LIST_ONLY_SUBCOMMANDS = {"stash": {"list", "show"}, "worktree": {"list"}}
FIND_WRITE_OPTIONS = frozenset(
    {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fls", "-fprint"}
)
FIND_WRITE_PREFIXES = ("-fprint",)
SED_PRINT_SCRIPT = re.compile(r"(\d+|\$)(,(\d+|\$))?p")
PYTHON_EXECUTABLE = re.compile(r"python(3(\.\d+)?)?(\.exe)?", re.IGNORECASE)
# 結果ファイルの出力先、Plugin読み込み、一時Directoryの指定は書き込みや任意実行になり得る。
PYTEST_WRITE_PREFIXES = (
    "--basetemp",
    "--cov",
    "--html",
    "--junit",
    "--report-log",
    "--result-log",
    "-p",
)
# 引数まで一致した場合だけ許可するRepositoryの確認Script。
ALLOWED_SCRIPT_ARGUMENTS = {
    "tools/check.py": (),
    "tools/sync_agent_config.py": ("--check",),
}


def _executable_name(token: str) -> str:
    """パスを除いた実行ファイル名を返す。"""

    return token.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]


def _tokenize(command: str) -> list[str] | None:
    """Shell演算子を分けたToken列を返す。解析できない場合はNoneを返す。"""

    # 改行は区切りとして実行されるがshlexでは空白になり、置換は任意のコマンドを実行する。
    if any(marker in command for marker in ("\n", "\r", "`", "$(")):
        return None
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def _segments(tokens: list[str]) -> Iterator[list[str]] | None:
    """演算子で区切ったコマンド列を返す。書き込み得る演算子があればNoneを返す。"""

    segments: list[list[str]] = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in COMMAND_SEPARATORS:
            segments.append([])
        elif token in REDIRECT_OPERATORS:
            target = tokens[index + 1] if index + 1 < len(tokens) else ""
            # 標準エラーの統合と/dev/nullへの破棄だけはファイルを作らない。
            if not (target == "/dev/null" or (token == ">&" and target in {"1", "2"})):
                return None
            current = segments[-1]
            if current and current[-1].isdigit():
                current.pop()
            index += 1
        elif token and set(token) <= set("();<>|&"):
            return None
        else:
            segments[-1].append(token)
        index += 1
    if any(not segment for segment in segments):
        return None
    return iter(segments)


def _allows_git(arguments: list[str]) -> bool:
    """Gitの引数が読み取りだけを行うか判定する。"""

    index = 0
    while index < len(arguments) and arguments[index].startswith("-"):
        option = arguments[index]
        if option in GIT_GLOBAL_FLAGS:
            index += 1
        elif option.split("=", 1)[0] in GIT_GLOBAL_OPTIONS_WITH_VALUE:
            index += 1 if "=" in option else 2
        else:
            return False
    if index >= len(arguments):
        return False
    subcommand, options = arguments[index], arguments[index + 1 :]
    if any(
        option.startswith(("--output", "--open-files-in-pager", "-O"))
        for option in options
    ):
        return False
    if subcommand in READ_ONLY_GIT_SUBCOMMANDS:
        return True
    if subcommand == "branch":
        return all(option in GIT_BRANCH_LIST_OPTIONS for option in options)
    if subcommand == "remote":
        return all(option in {"-v", "--verbose"} for option in options)
    allowed_actions = GIT_LIST_ONLY_SUBCOMMANDS.get(subcommand)
    return (
        allowed_actions is not None
        and options[:1] != []
        and (options[0] in allowed_actions)
    )


def _allows_python(arguments: list[str]) -> bool:
    """Pythonの引数が許可した確認処理だけを実行するか判定する。"""

    if arguments[:2] == ["-m", "pytest"]:
        return not any(
            argument.startswith(PYTEST_WRITE_PREFIXES) for argument in arguments[2:]
        )
    if not arguments:
        return False
    script = arguments[0].replace("\\", "/").removeprefix("./")
    expected = ALLOWED_SCRIPT_ARGUMENTS.get(script)
    return expected is not None and tuple(arguments[1:]) == expected


def _allows_segment(tokens: list[str]) -> bool:
    """1つのコマンドが追跡対象を変更しないか判定する。"""

    # `FOO=1 command`のような環境変数の上書きは実行内容を変え得る。
    if "=" in tokens[0] and not tokens[0].startswith("-"):
        return False
    name = _executable_name(tokens[0])
    arguments = tokens[1:]
    if name.lower() in {"git", "git.exe"}:
        return _allows_git(arguments)
    if PYTHON_EXECUTABLE.fullmatch(name):
        return _allows_python(arguments)
    if name == "find":
        return not any(
            argument in FIND_WRITE_OPTIONS or argument.startswith(FIND_WRITE_PREFIXES)
            for argument in arguments
        )
    if name == "sed":
        options = [argument for argument in arguments if argument.startswith("-")]
        positional = [
            argument for argument in arguments if not argument.startswith("-")
        ]
        return (
            options == ["-n"]
            and bool(positional)
            and SED_PRINT_SCRIPT.fullmatch(positional[0]) is not None
        )
    if name == "rg":
        return not any(argument.startswith("--pre") for argument in arguments)
    if name == "sort":
        return not any(
            argument.startswith(("-o", "--output")) for argument in arguments
        )
    return name in READ_ONLY_COMMANDS


def _is_read_only_agent(agent_type: str) -> bool:
    """正本のAgent定義が読み取り専用を宣言しているかを返す。"""

    # Agent名をパスとして解釈させないよう、定義ファイル名と完全一致する場合だけ読む。
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", agent_type):
        return False
    path = AGENT_DEFINITION_DIRECTORY / f"{agent_type}.toml"
    if not path.is_file():
        return False
    try:
        with path.open("rb") as source:
            definition = tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError):
        # 読み取り専用と宣言されたか確かめられないAgentは安全側で制限する。
        return True
    return definition.get("sandbox_mode") == "read-only"


def _blocked_reason(payload: Any) -> str | None:
    """拒否する理由を返す。許可する場合はNoneを返す。"""

    if not isinstance(payload, dict) or payload.get("hook_event_name") != "PreToolUse":
        return "Hook入力を解析できませんでした"
    agent_type = payload.get("agent_type")
    if not isinstance(agent_type, str) or not _is_read_only_agent(agent_type):
        return None
    tool_name = payload.get("tool_name")
    if tool_name != "Bash":
        return f"{tool_name}は読み取り専用のAgentで使用できません"

    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return "Shellコマンドを確認できませんでした"
    tokens = _tokenize(command)
    segments = _segments(tokens) if tokens else None
    if segments is None or not all(_allows_segment(segment) for segment in segments):
        return "読み取りと許可した確認コマンド以外は実行できません"
    return None


def _deny(reason: str) -> None:
    """Tool呼び出しを拒否するJSONを出力する。"""

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"読み取り専用ルールにより拒否しました: {reason}",
        }
    }
    # 既定コードページへ依存しないよう、非ASCII文字をエスケープして出力する。
    print(json.dumps(output, ensure_ascii=True))


def _use_utf8_output() -> None:
    """Windows CIなど非UTF-8のConsoleでも日本語の出力で失敗しないようにする。"""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    """標準入力のHook Payloadを検査する。"""

    _use_utf8_output()
    # Windowsの既定コードページへ依存せず、HookのJSONをUTF-8として読む。
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        _deny("Hook入力を解析できませんでした")
        return 0

    reason = _blocked_reason(payload)
    if reason is not None:
        _deny(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
