"""ローカルとCIで同じ品質ゲートを実行する。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MINIMUM_PYTHON = (3, 11)


@dataclass(frozen=True, slots=True)
class Check:
    """表示名とPythonモジュール形式のコマンドを保持する。"""

    name: str
    arguments: tuple[str, ...]


def _use_utf8_output() -> None:
    """Windows CIなど非UTF-8のConsoleでも日本語の出力で失敗しないようにする。"""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _run(check: Check) -> bool:
    """1つのチェックを実行し、成功したかを返す。"""

    command = [sys.executable, *check.arguments]
    print(f"\n==> {check.name}", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode != 0:
        print(f"\n失敗: {check.name}", file=sys.stderr, flush=True)
        return False
    return True


def _checks(fix: bool) -> tuple[Check, ...]:
    """指定モードで実行するチェック一覧を返す。"""

    if fix:
        format_arguments = ("-m", "ruff", "format", ".")
        lint_arguments = ("-m", "ruff", "check", "--fix", ".")
    else:
        format_arguments = ("-m", "ruff", "format", "--check", ".")
        lint_arguments = ("-m", "ruff", "check", ".")

    sync_arguments = ("tools/sync_agent_config.py",)
    if not fix:
        sync_arguments += ("--check",)

    return (
        Check("Claude Code設定の同期", sync_arguments),
        Check("Ruff format", format_arguments),
        Check("Ruff lint", lint_arguments),
        Check("mypy", ("-m", "mypy", "src")),
        Check("pytest", ("-m", "pytest")),
    )


def create_argument_parser() -> argparse.ArgumentParser:
    """品質ゲートの引数Parserを生成する。"""

    parser = argparse.ArgumentParser(
        description="KvK Team Builderの品質ゲートを実行します。"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Ruffの安全な自動修正を適用してから全チェックを実行する",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """品質ゲートを順に実行し、最初の失敗で終了する。"""

    _use_utf8_output()
    args = create_argument_parser().parse_args(argv)
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(map(str, MINIMUM_PYTHON))
        actual = f"{sys.version_info.major}.{sys.version_info.minor}"
        print(
            f"Python {required}以上が必要です（現在: {actual}）",
            file=sys.stderr,
        )
        return 2

    for check in _checks(args.fix):
        if not _run(check):
            print(
                '開発依存がない場合は python -m pip install -e ".[dev]" '
                "を実行してください。",
                file=sys.stderr,
            )
            return 1

    print("\nすべての品質チェックに成功しました。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
