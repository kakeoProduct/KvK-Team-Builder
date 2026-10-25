"""web/のHTMLを実物のままNode.jsとjsdomで動かす検査を実行する（ADR 0030）。"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DIRECTORY = PROJECT_ROOT / "tests" / "web"
NODE_VERSION_FILE = PROJECT_ROOT / ".node-version"
PACKAGE_FILE = PROJECT_ROOT / "package.json"
# 後始末の漏れで描画の予約が残っても、CIが止まり続けないようにする。
TEST_TIMEOUT_MS = 600_000

INSTALL_GUIDE = (
    "Node.jsとjsdomを入れてから再実行してください。\n"
    "  - Dev ContainerでNode.jsがない: `Dev Containers: Rebuild Container`で作り直す\n"
    "  - jsdomがないか版が違う: Repositoryの最上位で `npm ci` を実行する。"
    "Session用worktreeでは、そのworktreeの最上位で実行してもよい\n"
    "  - Containerを使わない環境: DEVELOPMENT.mdの「セットアップ」に従い、"
    ".node-versionの版のNode.jsを入れて `npm ci` を実行する"
)


def _use_utf8_output() -> None:
    """Windows CIなど非UTF-8のConsoleでも日本語の出力で失敗しないようにする。"""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def required_major_version() -> int:
    """`.node-version`に固定したNode.jsのメジャーバージョンを返す。"""

    text = NODE_VERSION_FILE.read_text(encoding="utf-8").strip()
    return int(text.split(".", 1)[0])


def required_jsdom_version() -> str:
    """`package.json`に固定したjsdomの版を返す。"""

    package = json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))
    return str(package["devDependencies"]["jsdom"])


def parse_major_version(output: str) -> int | None:
    """`node --version`の出力（例: v22.11.0）からメジャーバージョンを取り出す。"""

    matched = re.match(r"v(\d+)\.", output.strip())
    return int(matched.group(1)) if matched else None


def installed_jsdom_version(node: str) -> str | None:
    """検査と同じモジュール解決で見つかるjsdomの版を返す。見つからなければNone。

    Session用worktreeでは、Node.jsが親のDirectoryの`node_modules`も探すため、
    worktreeの直下だけを調べると、実際には動く検査を失敗扱いにしてしまう。
    """

    completed = subprocess.run(
        [node, "-p", "require('jsdom/package.json').version"],
        cwd=TEST_DIRECTORY,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def web_test_files() -> list[Path]:
    """実行する`tests/web/*.test.js`を名前順に返す。"""

    return sorted(TEST_DIRECTORY.glob("*.test.js"))


def create_argument_parser() -> argparse.ArgumentParser:
    """引数Parserを生成する。"""

    return argparse.ArgumentParser(
        description=(
            "web/の集結タイムライン計算と周期ウェーブタイマーを、"
            "Node.jsとjsdomで実物のまま検査します。"
        )
    )


def main(argv: list[str] | None = None) -> int:
    """Node.jsとjsdomを確かめてから、`node --test`で検査を実行する。"""

    _use_utf8_output()
    create_argument_parser().parse_args(argv)

    node = shutil.which("node")
    if node is None:
        print("Node.jsが見つかりません。", file=sys.stderr)
        print(INSTALL_GUIDE, file=sys.stderr)
        return 1

    version = subprocess.run(
        [node, "--version"], capture_output=True, text=True, check=False
    ).stdout
    major = parse_major_version(version)
    required = required_major_version()
    if major is None or major < required:
        print(
            f"Node.js {required}以上が必要です（現在: {version.strip() or '不明'}）。",
            file=sys.stderr,
        )
        print(INSTALL_GUIDE, file=sys.stderr)
        return 1

    jsdom = installed_jsdom_version(node)
    expected_jsdom = required_jsdom_version()
    if jsdom is None:
        print("jsdomが見つかりません。", file=sys.stderr)
        print(INSTALL_GUIDE, file=sys.stderr)
        return 1
    if jsdom != expected_jsdom:
        print(
            f"jsdom {expected_jsdom}が必要です（現在: {jsdom}）。",
            file=sys.stderr,
        )
        print(INSTALL_GUIDE, file=sys.stderr)
        return 1

    files = web_test_files()
    if not files:
        print(f"検査が見つかりません: {TEST_DIRECTORY}", file=sys.stderr)
        return 1

    # 絶対パスはNode.jsがglobとして読むため、最上位からの相対パスを`/`区切りで渡す。
    completed = subprocess.run(
        [
            node,
            "--test",
            "--test-reporter=spec",
            f"--test-timeout={TEST_TIMEOUT_MS}",
            *(path.relative_to(PROJECT_ROOT).as_posix() for path in files),
        ],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
