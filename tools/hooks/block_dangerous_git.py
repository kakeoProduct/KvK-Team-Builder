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
from itertools import chain
from typing import Any

COMMAND_SEPARATOR = re.compile(r"&&|\|\||[;|&\r\n]")
# 引用符を解釈しない、変更前（ADR 0033より前）の区切り。
PLAIN_SEPARATOR = re.compile(r"&&|\|\||[;|\r\n]")
# 語頭の`#`はコメントの始まりである。直前がこれらの文字か文頭のときだけ扱う。
COMMENT_START = {" ", "\t", "\n", ";", "&", "|", "(", ")"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
# Shellの値を取る長いOption。`-c`の文字列を探すときに値ごと読み飛ばす。
SHELL_LONG_OPTIONS_WITH_VALUE = {"--rcfile", "--init-file"}
# 区切りを引用符で囲むか`\`を付けたヒアドキュメント。本文は展開されない。引用符のない区切りの本文は展開されるため対象外。
# 区切りの語の途中で引用符が終わる形（`<<'E'OF`）は、区切りの読み違いを避けるため対象外とする。
HEREDOC = re.compile(
    r"""<<(-?)[ \t]*(?:'([^'\n]*)'|"([^"\n]*)"|\\([^\s;&|<>()]+))(?=[\s;&|<>()]|$)"""
)
# 区間の最初の語。`bash <<'E'`と`(bash <<'E'`の形で、本文をShellへ渡すかを見る。
FIRST_WORD = re.compile(r"[\s(]*([^\s;&|<>()]+)")
# 本文をパイプで受け取るShell。本文はコマンドとして実行される。
# パスの部分に`|`を含めない。`\S*`だと`|`が並ぶ行で`|`ごとに行末まで読み直し、時間が2乗で増える。
PIPE_TO_SHELL = re.compile(
    r"\|\s*(?:[^\s|]*[/\\])?(?:sh|bash|zsh|dash|ksh)(?:\.exe)?\b"
)
# 入れ子の判定の深さの上限。超えた分は判定しない。
MAX_NESTING = 8
# 引用符を解釈する判定を行う入力の長さの上限。超えた入力はADR 0033より前と同じ判定だけにする。
# 判定の時間に上限をかけ、時間切れのHookが判定を出さずに通常のpushの確認を落とすのを防ぐ。
MAX_QUOTE_AWARE_LENGTH = 20000
LINE_CONTINUATION = re.compile(r"\\\r?\n")
# 引用符の中の区切り文字を、語の中に残せる制御文字へ一時的に置き換える。
HIDDEN_SEPARATORS = {";": "\x1c", "|": "\x1d", "&": "\x1e", "\n": "\x1f", "\r": "\x19"}
RESTORED_SEPARATORS = str.maketrans({v: k for k, v in HIDDEN_SEPARATORS.items()})
# 閉じた引用符の中の空白を保ち、閉じていない引用符は語の一部として読む。
LOOSE_WORD = re.compile(r"""(?:"[^"]*"|'[^']*'|\S)+""")
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


def _command_segments(command: str, depth: int = 0) -> Iterator[list[str]]:
    """Shellコマンドを区切り、区間ごとのToken列を返す。

    事故を防ぐための照合であり、Shellを正確には解釈しない。閉じた引用符の中の区切り文字は
    区切りとして扱わない。コメントの`'`などで字句解析に失敗した区間も読み飛ばさず、語に分けて
    同じ判定にかける。失敗しただけで拒否すると、本文に`'`を含むヒアドキュメントなど日常の
    コマンドが止まる（ADR 0033）。行末の`\\`が行継続か見分けられないため、連結の前と後の両方を
    判定する。ただし、`$(...)`、バッククォート、`sh -c`、`eval`の文字列はShellが実行するため、
    二重引用符の中にあっても中身を別のコマンドとして判定する。単一引用符、コメント、引用符付きの
    ヒアドキュメントの本文の置換は実行されないため除く。
    """

    if depth > MAX_NESTING:
        return
    text, substitutions = _scan_quotes(command)
    for substitution in substitutions:
        yield from _command_segments(substitution, depth + 1)
    # 行継続がなければ2つの候補は同じ文になる。入れ子ごとに判定が2倍に増えないよう1回にする。
    for candidate in dict.fromkeys((text, LINE_CONTINUATION.sub(" ", text))):
        for segment in COMMAND_SEPARATOR.split(candidate):
            try:
                tokens = shlex.split(segment, posix=True)
            except ValueError:
                words = LOOSE_WORD.findall(segment)
                tokens = [re.sub("[\"']", "", word) for word in words]
            # `(git reset --hard)`のSubshellの括弧は、コマンド名とOptionに含めない。
            tokens = [
                word
                for token in tokens
                if (
                    word := token.translate(RESTORED_SEPARATORS).lstrip("(").rstrip(")")
                )
            ]
            if tokens:
                yield tokens
                script = _shell_script(tokens)
                if script is not None:
                    yield from _command_segments(script, depth + 1)


def _scan_quotes(command: str) -> tuple[str, list[str]]:
    """引用符の範囲を左から走査し、引用符の中の区切りを隠した文と、別に判定する文を返す。

    別に判定する文は、置換の中身と、Shellへ渡すヒアドキュメントの本文である。`\\`の退避と
    改行をまたぐ引用符をShellと同じく扱う。正規表現で範囲を決めると、`'\\''`や`\\"`で範囲が
    ずれ、引用符の外の区切りまで隠して後ろの操作を見逃す。最後まで引用符が閉じなければ
    （引用符のないヒアドキュメントの本文の`'`など）、範囲を信用せず、区切りを隠さない元の文を
    返す。単一引用符、コメント、引用符付きのヒアドキュメントの本文の`$(...)`とバッククォートは
    実行されないため、判定しない。
    """

    hidden: list[str] = []
    substitutions: list[str] = []
    closing = _matching_parens(command)
    heredocs: list[tuple[str, bool, bool]] = []
    # 本文をShellへ渡すかの判定に使う、区間の始まりと、行ごとのパイプの有無。
    segment_start = 0
    line_end = -1
    pipes_to_shell = False
    # 区間ごとに1回だけ、最初の語がShellかを判定する。記号ごとに区間の先頭から読み直さない。
    shell_segment: tuple[int, bool] = (-1, False)
    quote: str | None = None
    index = 0
    while index < len(command):
        char = command[index]
        if quote == "'":
            quote = None if char == "'" else quote
            hidden.append(HIDDEN_SEPARATORS.get(char, char))
            index += 1
            continue
        if quote is None and char == "\n" and heredocs:
            # 引用符付きのヒアドキュメントの本文はデータであり、Shellは展開しない。区切りの
            # 判定から除き、本文をShellへ渡すときだけコマンドとして判定する。
            hidden.append(char)
            index, scripts = _skip_heredoc_bodies(command, index + 1, heredocs)
            substitutions.extend(scripts)
            heredocs.clear()
            segment_start = index
            continue
        heredoc = _heredoc_at(command, index) if quote is None else None
        if heredoc is not None:
            delimiter, strips_tabs, end = heredoc
            # 記号ごとに行の残りを探し直すと、記号が並んだ行で時間が2乗で増える。行ごとに1回だけ探す。
            if end > line_end:
                found = command.find("\n", end)
                line_end = len(command) if found < 0 else found
                pipes_to_shell = (
                    PIPE_TO_SHELL.search(command, end, line_end) is not None
                )
            if shell_segment[0] != segment_start:
                starts = _starts_with_shell(command, segment_start)
                shell_segment = (segment_start, starts)
            feeds_shell = pipes_to_shell or shell_segment[1]
            heredocs.append((delimiter, strips_tabs, feeds_shell))
            hidden.append(command[index:end])
            index = end
            continue
        if char == "\\" and index + 1 < len(command):
            following = command[index + 1]
            # 引用符の外の行継続は、連結の前と後の両方で判定するため、そのまま残す。
            if quote is None and following in "\r\n":
                hidden.append(char + following)
            else:
                hidden.append(char + HIDDEN_SEPARATORS.get(following, following))
            index += 2
            continue
        end = _substitution_end(command, index, closing)
        if end is not None:
            start = index + (2 if char == "$" else 1)
            substitutions.append(command[start : end - 1])
            hidden.append(_hide(command[index:end]))
            index = end
            continue
        if (
            char == "#"
            and quote is None
            and (not hidden or hidden[-1][-1:] in COMMENT_START)
        ):
            # コメントの中の引用符と置換はShellが解釈しないため、行末までそのまま写す。
            end = command.find("\n", index)
            end = len(command) if end < 0 else end
            hidden.append(command[index:end])
            index = end
            continue
        if char == "'" and quote is None:
            quote = "'"
        elif char == '"':
            quote = None if quote == '"' else '"'
        hidden.append(_hide(char) if quote is not None else char)
        if quote is None and char in ";&|\n":
            segment_start = index + 1
        index += 1
    if quote is not None:
        return command, substitutions
    return "".join(hidden), substitutions


def _heredoc_at(command: str, index: int) -> tuple[str, bool, int] | None:
    """引用符付きのヒアドキュメントが始まる位置なら、区切り、タブの除去、終わりの位置を返す。"""

    # `<<<`はヒアストリングで、本文を持たない。`<<<'x'`の2文字目からの一致を除く。
    if index > 0 and command[index - 1] == "<":
        return None
    match = HEREDOC.match(command, index)
    if match is None:
        return None
    delimiter = next(group for group in match.groups()[1:] if group is not None)
    return delimiter, match[1] == "-", match.end()


def _starts_with_shell(command: str, segment_start: int) -> bool:
    """区間の最初の語がShellか（`bash <<'E'`、`(bash <<'E'`）を返す。"""

    first = FIRST_WORD.match(command, segment_start)
    return first is not None and _command_name(first[1]) in SHELLS


def _command_name(token: str) -> str:
    """パスと`.exe`を除いたコマンド名を返す。"""

    return token.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower().removesuffix(".exe")


def _skip_heredoc_bodies(
    command: str, index: int, heredocs: list[tuple[str, bool, bool]]
) -> tuple[int, list[str]]:
    """ヒアドキュメントの本文を区切りの行まで読み飛ばし、続きの位置と、Shellへ渡す本文を返す。"""

    scripts: list[str] = []
    for delimiter, strips_tabs, feeds_shell in heredocs:
        lines: list[str] = []
        while index < len(command):
            end = command.find("\n", index)
            end = len(command) if end < 0 else end + 1
            line = command[index:end]
            index = end
            body = line.rstrip("\r\n")
            if (body.lstrip("\t") if strips_tabs else body) == delimiter:
                break
            lines.append(line)
        if feeds_shell:
            scripts.append("".join(lines))
    return index, scripts


def _plain_segments(command: str) -> Iterator[list[str]]:
    """ADR 0033より前と同じく、引用符を解釈せずに区切りで分けた区間を返す。

    区切りは`;`、`|`、`&&`、`||`、改行で、単独の`&`では分けない。

    引用符の範囲の解釈がShellとずれても、ADR 0033より前に拒否または確認していた入力を緩めないため、この判定も
    必ず行い、厳しいほうを採る。字句解析に失敗した区間は、ADR 0033より前と同じく読み飛ばす。
    """

    for segment in PLAIN_SEPARATOR.split(command):
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            continue
        if tokens:
            yield tokens


def _matching_parens(command: str) -> dict[int, int]:
    """開き括弧の位置から、対応する閉じ括弧の位置を返す。

    1回の走査で求める。`$(`ごとに末尾まで数えると、閉じない`$(`が並んだ入力で時間が長さの
    2乗で増え、Hookが時間切れになり得る。単一引用符、二重引用符、コメント、引用符付きの
    ヒアドキュメントの本文の括弧と、`\\`で退避した括弧は数えない。`$(`の中では引用符の状態を
    新しく始め、閉じたら外側の状態へ戻す。コミットの
    本文の`1)`で`$(`の範囲を誤ると、本文のバッククォートを置換として判定してしまう。
    """

    closing: dict[int, int] = {}
    # 開き括弧の位置と、閉じたときに戻す引用符の状態。
    opened: list[tuple[int, str | None]] = []
    heredocs: list[tuple[str, bool, bool]] = []
    quote: str | None = None
    index = 0
    while index < len(command):
        char = command[index]
        if quote == "'":
            quote = None if char == "'" else quote
            index += 1
            continue
        if quote is None and char == "\n" and heredocs:
            index, _ = _skip_heredoc_bodies(command, index + 1, heredocs)
            heredocs.clear()
            continue
        if char == "\\":
            index += 2
            continue
        heredoc = _heredoc_at(command, index) if quote is None else None
        if heredoc is not None:
            heredocs.append((heredoc[0], heredoc[1], False))
            index = heredoc[2]
            continue
        if (
            char == "#"
            and quote is None
            and (index == 0 or command[index - 1] in COMMENT_START)
        ):
            line_end = command.find("\n", index)
            index = len(command) if line_end < 0 else line_end
            continue
        if command.startswith("$(", index):
            opened.append((index + 1, quote))
            quote = None
            index += 2
            continue
        if quote is None and char == "(":
            opened.append((index, None))
        elif quote is None and char == ")" and opened:
            position, quote = opened.pop()
            closing[position] = index
        elif char == "'" and quote is None:
            quote = "'"
        elif char == '"':
            quote = None if quote == '"' else '"'
        index += 1
    return closing


def _substitution_end(command: str, index: int, closing: dict[int, int]) -> int | None:
    """`$(...)`かバッククォートが始まる位置なら、その終わりの次の位置を返す。"""

    if command.startswith("$(", index):
        end = closing.get(index + 1)
        return None if end is None else end + 1
    if command[index] == "`":
        position = index + 1
        while position < len(command):
            if command[position] == "\\":
                position += 2
                continue
            if command[position] == "`":
                return position + 1
            position += 1
    return None


def _hide(text: str) -> str:
    """区切り文字を、区切りとして読まれない文字へ置き換える。"""

    return "".join(HIDDEN_SEPARATORS.get(char, char) for char in text)


def _shell_script(tokens: list[str]) -> str | None:
    """`sh -c`や`eval`でShellへ渡す文字列を返す。"""

    index = 0
    while index < len(tokens):
        name = _command_name(tokens[index])
        if name == "eval":
            return " ".join(tokens[index + 1 :]) or None
        if name not in SHELLS:
            index += 1
            continue
        # bashは`-c`の後もOptionを読み、Optionと`--`の後の最初の語を文字列とする。
        reads_command = False
        position = index + 1
        while position < len(tokens):
            option = tokens[position]
            # bashは`-`も`--`と同じくOptionの終わりとして扱う。
            if option in {"--", "-"}:
                position += 1
                break
            if option in SHELL_LONG_OPTIONS_WITH_VALUE:
                position += 2
            elif option.startswith("--"):
                position += 1
            elif option[:1] in {"-", "+"} and len(option) > 1:
                letters = option[1:]
                reads_command = reads_command or (option[0] == "-" and "c" in letters)
                # `-o pipefail`や`-euo pipefail`のように、`o`と`O`は次の語を値に取る。
                position += 2 if ("o" in letters or "O" in letters) else 1
            else:
                break
        if reads_command and position < len(tokens):
            return tokens[position]
        # 読み飛ばした語はOptionかその値で、コマンドの名前ではない。`bash -o bash -o …`で
        # 同じ語から走査を始め直すと、時間が語数の2乗で増える。
        index = max(position, index + 1)
    return None


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
    """拒否対象の操作名を返す。

    ADR 0033より前と同じ判定と、引用符を解釈する判定（`MAX_QUOTE_AWARE_LENGTH`以下の入力だけ）の厳しい
    ほうを返す。拒否を通常のpushの確認より優先する。
    """

    pushes = False
    # ADR 0033より前と同じ判定を先に行い、引用符を解釈する判定に左右されずに拒否を返す。
    quote_aware = (
        _command_segments(command) if len(command) <= MAX_QUOTE_AWARE_LENGTH else ()
    )
    for tokens in chain(_plain_segments(command), quote_aware):
        arguments = _git_arguments(tokens)
        if not arguments:
            continue

        subcommand = arguments[0].lower()
        options = arguments[1:]
        if subcommand == "push":
            if _is_force_push(options):
                return "git push --force"
            # 通常のpushは確認で済むため、後ろの区間の拒否を優先する。
            pushes = True
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
    return PUSH_OPERATION if pushes else None


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
    # 深い入れ子のRecursionErrorと巨大な整数のValueErrorも含め、例外で判定なしに終わらせない。
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (ValueError, RecursionError):
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
