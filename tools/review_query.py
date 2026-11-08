"""読み取り専用のReview Agentが、検索、履歴、テストを扱う固定の入口。

Claude CodeのReview AgentはBashでこのScriptだけを実行できる。Hookは呼び出しの形だけを確かめ、
GitとpytestのOptionの意味はここへ閉じ込める（ADR 0033）。担当が渡せるのはパス、リビジョン、
検索語、`tests/`の下のpytestのテストの指定だけで、外部のコマンドへOptionとして渡る値は受け付けない。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 担当が並列に動くため、任意のロックを取らない。
GIT = ("git", "--no-pager", "--no-optional-locks", "-c", "core.quotePath=false")
LIST_FILES = ("ls-files", "--cached", "--others", "--exclude-standard")
REVISION = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./~^@-]*")
TEST_NODE = re.compile(r"[A-Za-z0-9_.:\[\]-]*")
# 一致がないときのgit grepの終了コード。エラーではない。
GREP_NO_MATCH = 1
DEFAULT_LOG_LIMIT = 30


class QueryError(ValueError):
    """閉じた形から外れた引数を表す。"""


def _path(value: str) -> str:
    """Repositoryの中を指す相対パスだけを返す。"""

    # `:`はGitのpathspecの魔法とWindowsのドライブ指定になり得るため受け付けない。
    if (
        not value
        or value.startswith(("/", "-"))
        or "\\" in value
        or ":" in value
        or ".." in value.split("/")
    ):
        raise QueryError(f"Repositoryの中の相対パスを指定してください: {value!r}")
    return value


def _revision(value: str) -> str:
    """Optionとして読まれないリビジョンだけを返す。"""

    if REVISION.fullmatch(value) is None:
        raise QueryError(f"リビジョンの形が正しくありません: {value!r}")
    return value


def _blob(value: str) -> str:
    """`<リビジョン>:<パス>`の形だけを返す。"""

    revision, separator, path = value.partition(":")
    if not separator:
        raise QueryError(f"`<リビジョン>:<パス>`で指定してください: {value!r}")
    return f"{_revision(revision)}:{_path(path)}"


def _test_target(value: str) -> str:
    """`tests/`の下のパスとノードIDだけを返す。"""

    path, separator, node = value.partition("::")
    checked = _path(path)
    if not (checked == "tests" or checked.startswith("tests/")):
        raise QueryError(f"`tests/`の下を指定してください: {value!r}")
    if TEST_NODE.fullmatch(node) is None:
        raise QueryError(f"テストの指定の形が正しくありません: {value!r}")
    return f"{checked}{separator}{node}"


def _positive(value: str) -> int:
    """1以上の整数だけを返す。"""

    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(f"1以上の整数を指定してください: {value!r}")
    return number


def _pathspec(paths: Sequence[str]) -> list[str]:
    """パスの指定をGitの引数へ変換する。"""

    checked = [_path(path) for path in paths]
    return ["--", *checked] if checked else []


def _command(args: argparse.Namespace) -> tuple[list[str], tuple[int, ...]]:
    """実行するコマンドと、成功として扱う終了コードを返す。"""

    git = list(GIT)
    if args.query == "status":
        return [*git, "status", "--short", "--untracked-files=all"], (0,)
    if args.query == "list":
        return [*git, *LIST_FILES, *_pathspec(args.paths)], (0,)
    if args.query == "grep":
        search = ["grep", "-n", "-I", "--untracked", "-E"]
        if args.ignore_case:
            search.append("-i")
        command = [*git, *search, "-e", args.pattern, *_pathspec(args.paths)]
        return command, (0, GREP_NO_MATCH)
    if args.query == "diff":
        diff = ["diff", "--no-ext-diff", "--no-textconv"]
        if args.stat:
            diff.append("--stat")
        diff += ["--merge-base", _revision(args.base)]
        return [*git, *diff, *_pathspec(args.path)], (0,)
    if args.query == "log":
        form = "--format=%h %s%n%b" if args.body else "--oneline"
        log = ["log", form, f"-n{args.limit}"]
        if args.range is not None:
            log.append(_revision(args.range))
        return [*git, *log, *_pathspec(args.path)], (0,)
    if args.query == "show":
        show = ["show", "--no-ext-diff", "--no-textconv", _blob(args.blob)]
        return [*git, *show], (0,)
    if args.query == "commit":
        commit = ["show", "--no-ext-diff", "--no-textconv", _revision(args.revision)]
        return [*git, *commit], (0,)
    targets = [_test_target(target) for target in args.targets]
    return [sys.executable, "-m", "pytest", "-q", "--", *targets], (0,)


def _ensure_paths_have_files(paths: Sequence[str], root: Path) -> None:
    """Gitが対象にしないパスを、一致なしと区別できるようエラーにする。"""

    for path in paths:
        listed = subprocess.run(
            [*GIT, *LIST_FILES, "--", path], cwd=root, capture_output=True, check=False
        )
        if listed.returncode == 0 and not listed.stdout.strip():
            raise QueryError(
                f"対象のファイルがありません: {path!r}。"
                "`tmp/`などGit管理外のファイルはReadで読んでください"
            )


def create_argument_parser() -> argparse.ArgumentParser:
    """引数Parserを生成する。"""

    parser = argparse.ArgumentParser(
        prog="review_query.py",
        description="レビュー担当のための読み取り専用の確認を行います。",
        allow_abbrev=False,
    )
    queries = parser.add_subparsers(dest="query", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        return queries.add_parser(
            name, help=help_text, description=help_text, allow_abbrev=False
        )

    add("status", "変更と未追跡のファイルを1件ずつ示す")
    listing = add("list", "追跡中と未追跡のファイルを一覧にする")
    listing.add_argument("paths", nargs="*", help="対象のパス")
    search = add(
        "grep",
        "追跡中と未追跡のファイルを拡張正規表現で検索する。Optionは検索語より前に書き、"
        "`-`で始まる検索語は`--`の後に書く",
    )
    search.add_argument(
        "--ignore-case", action="store_true", help="大文字小文字を区別しない"
    )
    search.add_argument("pattern", help="検索する拡張正規表現")
    search.add_argument("paths", nargs="*", help="対象のパス")
    diff = add(
        "diff",
        "基準との分岐点から作業ツリーまでの差分を示す。未追跡のファイルは出ないため、"
        "`status`で確かめてReadで読む",
    )
    diff.add_argument("--base", default="HEAD", help="基準のリビジョン（既定: HEAD）")
    diff.add_argument(
        "--stat", action="store_true", help="ファイルごとの増減だけを示す"
    )
    diff.add_argument("--path", action="append", default=[], help="対象のパス")
    log = add("log", "コミットの一覧を示す")
    log.add_argument("--range", help="リビジョンまたは範囲（例: dev..HEAD）")
    log.add_argument(
        "--limit", type=_positive, default=DEFAULT_LOG_LIMIT, help="最大の件数"
    )
    log.add_argument("--body", action="store_true", help="コミットの本文も示す")
    log.add_argument("--path", action="append", default=[], help="対象のパス")
    show = add("show", "過去の版のファイルを示す")
    show.add_argument("blob", help="`<リビジョン>:<パス>`")
    commit = add("commit", "1つのコミットの本文と差分を示す")
    commit.add_argument("revision", help="リビジョン")
    test = add("test", "`tests/`の下のpytestのテストを実行する")
    test.add_argument("targets", nargs="+", help="テストのパスまたはノードID")
    return parser


def _use_utf8_output() -> None:
    """Windows CIなど非UTF-8のConsoleでも日本語の出力で失敗しないようにする。"""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None, root: Path = PROJECT_ROOT) -> int:
    """指定された確認を実行し、終了コードを返す。"""

    _use_utf8_output()
    try:
        args = create_argument_parser().parse_args(argv)
        command, success_codes = _command(args)
        if args.query in {"list", "grep"}:
            _ensure_paths_have_files(args.paths, root)
    except QueryError as error:
        print(str(error), file=sys.stderr)
        return 2
    except OSError as error:
        print(f"コマンドを実行できませんでした: {error}", file=sys.stderr)
        return 2
    except SystemExit as stop:
        # Hookの判定と同じく、引数の誤りは例外ではなく終了コードで返す。
        return stop.code if isinstance(stop.code, int) else 2

    try:
        completed = subprocess.run(
            command,
            cwd=root,
            check=False,
            capture_output=True,
            # 親の再設定は子のpytestへ届かないため、日本語の出力をUTF-8に固定する。
            env={**os.environ, "PYTHONUTF8": "1"},
        )
    except OSError as error:
        print(f"コマンドを実行できませんでした: {error}", file=sys.stderr)
        return 2
    # Gitとpytestの出力はバイト列のまま渡し、Consoleの文字コードで変換しない。
    for stream, content in (
        (sys.stdout, completed.stdout),
        (sys.stderr, completed.stderr),
    ):
        if content:
            stream.buffer.write(content)
            stream.flush()
    return 0 if completed.returncode in success_codes else completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
