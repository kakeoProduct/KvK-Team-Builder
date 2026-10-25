"""読み取り専用のReview AgentのTool呼び出しを、権限モードにかかわらず制限する。

Claude Codeでは親Sessionが`auto`、`acceptEdits`、`bypassPermissions`のとき、Subagentの
`permissionMode: plan`が無視される。PreToolUse Hookの拒否は権限モードより先に評価される
ため、`.claude/settings.json`へ登録して`plan`相当の制限を強制する。Subagent定義の
Frontmatterへ書いたHookは、Agentファイルのあるフォルダそのものを信頼したときだけ動き、
`claude -p`では動かないため使わない（ADR 0031）。

Codexもcustom agentの`sandbox_mode`を適用せず、Subagentは親のsandboxと承認設定を継承する。
このため`.codex/hooks.json`へも登録する。CodexもSubagent内のHook入力へ`agent_type`を入れ、
Shellを`Bash`、編集を`apply_patch`として同じ形で渡す（ADR 0031）。

Hook入力の`agent_type`が、正本の`.codex/agents/`で`sandbox_mode = "read-only"`と宣言した
Agentのときだけ制限する。主Sessionと他のAgentのTool呼び出しは判定せず通す。

両方の設定のmatcherは、書き込み得るTool（Bash、編集Tool、Agentの起動、MCPなど）だけを
このHookへ渡す。読み取りToolと内部Toolでは起動しないため、内部Toolが増えても結果の返却を
妨げない。制限対象のAgentでは、届いたToolのうちBashの許可した確認コマンドだけを通し、
それ以外と解析できない入力は拒否する。
"""

from __future__ import annotations

import json
import os
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
# findは実装（GNU find、bfs）ごとに削除や実行のOptionが違うため、検索の条件と出力だけを許可する。
# Claude Codeの`find`はbfsで、`-delete`の別名の`-rm`を持つ。
FIND_OPTIONS_WITH_VALUE = frozenset(
    {
        "-iname",
        "-ipath",
        "-iregex",
        "-maxdepth",
        "-mindepth",
        "-mmin",
        "-mtime",
        "-name",
        "-newer",
        "-path",
        "-regex",
        "-size",
        "-type",
    }
)
FIND_FLAGS = frozenset(
    {
        "!",
        "-a",
        "-and",
        "-depth",
        "-empty",
        "-ls",
        "-not",
        "-o",
        "-or",
        "-print",
        "-print0",
        "-prune",
        "-quit",
    }
)
SED_PRINT_SCRIPT = re.compile(r"\d+(,\d+)?p")
PYTHON_EXECUTABLE = re.compile(r"python(3(\.\d+)?)?(\.exe)?", re.IGNORECASE)
# pytestは結果ファイルの出力、Plugin、設定の上書き（`-o addopts=...`）、対話のデバッガー、
# 外部への送信で書き込みや任意実行になり得るため、出力の量と対象を選ぶOptionだけを許可する。
PYTEST_FLAG = re.compile(r"-[qvxls]+|-r[a-zA-Z]+")
PYTEST_LONG_FLAGS = frozenset(
    {
        "--collect-only",
        "--co",
        "--exitfirst",
        "--failed-first",
        "--ff",
        "--last-failed",
        "--lf",
        "--no-header",
        "--quiet",
        "--verbose",
    }
)
PYTEST_VALUE_PREFIXES = ("--durations=", "--maxfail=", "--tb=")
# 次の引数を値として取るOption。値はテストの選択式で、ファイルを指さない。
PYTEST_OPTIONS_WITH_VALUE = frozenset({"-k", "-m"})
# sortはOptionの省略形を受け付け、出力先や圧縮Programを指定できるため、並べ方だけを許可する。
SORT_FLAG = re.compile(r"-(?=.)[bfhnrsuV]*(?:[kt].*)?")
# Gitの長いOptionは一意な省略形でも受け付けるため、書き込みやPagerの起動につながるOptionは
# 省略形も拒否する。
GIT_DANGEROUS_LONG_OPTIONS = ("--output", "--open-files-in-pager")
# CodexはShellの種類を問わず`Bash`として渡すため、POSIXのShellとして判定する。POSIXと
# 解釈が食い違う記号は、1つずつ並べず丸ごと拒否する。PowerShellは`{}`をScript Blockとして
# 実行し、全角の引用符も引用符として扱う。
POSIX_MISMATCH_MARKERS = ("{", "}", "“", "”", "„", "‘", "’")
# `$`は変数の展開（`$_`など）でHookが見ていない引数を渡し、`\`はPowerShellとcmdではエスケープに
# ならず語の区切りが変わる。
SHELL_EXPANSION_MARKERS = ("$", "\\")
# cmdは単一引用符を引用符として扱わず、`^`でエスケープし、`%VAR%`と（遅延展開が有効なら）`!VAR!`を
# 展開し、`sort /O`で書き込む。
WINDOWS_SHELL = os.name == "nt"
WINDOWS_ONLY_MARKERS = ("'", "^", "%", "!")
# ripgrepの外部コマンドを起動するOption。
RG_COMMAND_OPTIONS = ("--pre", "--hostname-bin")
# 拒否したときに、許可リストに合わせた書き方を示す。
DENIED_COMMAND_REASON = (
    "読み取りと許可した確認コマンド以外は実行できません。pytest、sort、findは許可したOptionだけを使い、"
    "値は`--tb=short`のように`=`で付けてください。短いOptionの値は`-S Optimizer`のように空白で"
    "分けてください"
)
# 引数まで一致した場合だけ許可するRepositoryの確認Script。
ALLOWED_SCRIPT_ARGUMENTS = {
    "tools/check.py": (),
    "tools/sync_agent_config.py": ("--check",),
}


def _executable_name(token: str) -> str:
    """パスを除いた実行ファイル名を返す。"""

    # `\`を含むコマンドは先に拒否するが、判定の順序が変わっても名前を取り違えないよう残す。
    return token.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]


def _tokenize(command: str) -> list[str] | None:
    """Shell演算子を分けたToken列を返す。解析できない場合はNoneを返す。"""

    # 改行は区切りとして実行されるがshlexでは空白になり、置換は任意のコマンドを実行する。
    if any(marker in command for marker in ("\n", "\r", "`", "$(")):
        return None
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    # bashは語の途中の`#`を注釈にしないため、shlexの注釈の処理を無効にする。
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return None


def _posix_mismatch(command: str) -> str | None:
    """POSIXと解釈が食い違う記号があれば、言い換えの手がかりを含む理由を返す。"""

    if any(marker in command for marker in POSIX_MISMATCH_MARKERS):
        return (
            "PowerShellと解釈が食い違う`{}`と全角の引用符は使えません。"
            "`HEAD@{1}`のような参照はコミットのSHAで言い換えてください"
        )
    if any(marker in command for marker in SHELL_EXPANSION_MARKERS):
        return (
            "Shellごとに解釈が違う`$`と`\\`は使えません。パスは`/`で区切り、変数を使わずに"
            "書いてください。ファイルの末尾は`tail`で読んでください。検索の正規表現は、行全体は`-x`、"
            '語の境界は`-w`、`.`は`[.]`、固定の文字列は`-F`、選択は`grep -E "a|b"`で書いてください'
        )
    if WINDOWS_SHELL and any(marker in command for marker in WINDOWS_ONLY_MARKERS):
        return (
            "Windowsでは単一引用符、`^`、`%`、`!`は使えません。二重引用符で言い換え、"
            "`HEAD^`は`HEAD~1`、`--format=%h`は`--oneline`、findの`!`は`-not`と書いてください"
        )
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
    if any(_is_dangerous_git_option(option) for option in options):
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


def _is_dangerous_git_option(option: str) -> bool:
    """書き込みやPagerの起動につながるGitのOptionを、省略形を含めて判定する。"""

    # 短いOptionは`-nO<cmd>`のように束ねられ、`-O`の残りがPagerのコマンドになる。
    if option.startswith("-") and not option.startswith("--") and "O" in option:
        return True
    name = option.split("=", 1)[0]
    # `--o`のような短すぎる省略形は複数のOptionに当たり得るが、安全側で拒否する。
    return len(name) > 2 and any(
        long_option.startswith(name) for long_option in GIT_DANGEROUS_LONG_OPTIONS
    )


def _allows_pytest(arguments: list[str]) -> bool:
    """pytestの引数が、許可したOptionとテストの指定だけかを判定する。"""

    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in PYTEST_OPTIONS_WITH_VALUE:
            # 値の位置でも`@file`はファイルのOptionとして展開される。
            if index + 1 < len(arguments) and arguments[index + 1].startswith("@"):
                return False
            index += 2
            continue
        # `@file`は、ファイルに書いたOptionを読み込む。
        if argument.startswith("@"):
            return False
        if argument.startswith("-") and not (
            PYTEST_FLAG.fullmatch(argument)
            or argument in PYTEST_LONG_FLAGS
            or argument.startswith(PYTEST_VALUE_PREFIXES)
        ):
            return False
        index += 1
    return True


def _allows_sort(arguments: list[str]) -> bool:
    """sortの引数が、並べ方のOptionと入力ファイルだけかを判定する。"""

    for argument in arguments:
        if argument.startswith("-") and not SORT_FLAG.fullmatch(argument):
            return False
        # cmdの`sort.exe`は`/O`で出力先を指定する。
        if WINDOWS_SHELL and argument.startswith("/"):
            return False
    return True


def _allows_find(arguments: list[str]) -> bool:
    """findの引数が、検索の起点、許可した条件、出力だけかを判定する。"""

    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in FIND_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if (argument.startswith("-") or argument == "!") and argument not in FIND_FLAGS:
            return False
        index += 1
    return True


def _allows_python(arguments: list[str]) -> bool:
    """Pythonの引数が許可した確認処理だけを実行するか判定する。"""

    if arguments[:2] == ["-m", "pytest"]:
        return _allows_pytest(arguments[2:])
    if not arguments:
        return False
    # `\`を含むコマンドは先に拒否するため、置き換えは判定の順序が変わったときの防御として残す。
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
        return _allows_find(arguments)
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
        return not any(
            argument.startswith(RG_COMMAND_OPTIONS) for argument in arguments
        )
    if name == "sort":
        return _allows_sort(arguments)
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
    mismatch = _posix_mismatch(command)
    if mismatch is not None:
        return mismatch
    tokens = _tokenize(command)
    segments = _segments(tokens) if tokens else None
    if segments is None or not all(_allows_segment(segment) for segment in segments):
        return DENIED_COMMAND_REASON
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
