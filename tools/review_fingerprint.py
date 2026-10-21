"""レビューした変更の指紋を計算する（ADR 0024）。

`$review-kvk-change`は、レビューの基準のコミットからの変更（未コミットの変更と未追跡の
ファイルを含む）をこの指紋で記録する。変更がない場合も記録する。`$review-kvk-change`、`$create-github-pr`、
`$implement`は、コミット後の範囲から同じ指紋を計算し、
一致すればレビューした変更だけがコミットされたとみなして結果を投稿する。
共有記憶（`docs/project-memory/`）はレビューの後に記録するため、指紋に含めない。
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PREFIX = "docs/project-memory/"
DELETED = "deleted"


def _git(repository: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=repository, check=True, capture_output=True
    ).stdout


def _split(output: bytes) -> list[str]:
    return [path.decode("utf-8") for path in output.split(b"\0") if path]


def _changed_paths(repository: Path, base: str, target: str | None) -> list[str]:
    # 名前の変更を検出すると変更前のパスが出ず、作業ツリーとコミットで結果が変わるため検出しない
    diff = ("diff", "--no-renames", "--name-only", "-z", base)
    if target is None:
        paths = _split(_git(repository, *diff))
        paths += _split(
            _git(repository, "ls-files", "--others", "--exclude-standard", "-z")
        )
    else:
        paths = _split(_git(repository, *diff, target))
    return sorted({path for path in paths if not path.startswith(EXCLUDED_PREFIX)})


def _blob(repository: Path, path: str, target: str | None) -> str:
    if target is None:
        if not (repository / path).is_file():
            return DELETED
        return _git(repository, "hash-object", "--", path).decode().strip()
    listed = _git(repository, "ls-tree", "-z", target, "--", path)
    if not listed:
        return DELETED
    return listed.split(b"\t", 1)[0].split()[2].decode()


def fingerprint(repository: Path, base: str, target: str | None = None) -> str:
    """基準のコミットから作業ツリー、または指定したコミットまでの変更の指紋を返す。"""

    lines = [
        f"{path}\t{_blob(repository, path, target)}"
        for path in _changed_paths(repository, base, target)
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="レビューした変更の指紋を計算する。")
    parser.add_argument("--base", required=True, help="レビューした基準のコミット")
    parser.add_argument(
        "--target",
        help="比べるコミット。省略すると作業ツリー（未追跡のファイルを含む）を使う",
    )
    return parser


def main(argv: list[str] | None = None, root: Path = PROJECT_ROOT) -> int:
    """指紋を標準出力へ書く。"""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            # Windows CIなど非UTF-8のConsoleでも日本語の出力で失敗しないようにする。
            reconfigure(encoding="utf-8", errors="replace")
    args = create_argument_parser().parse_args(argv)
    for value in (args.base, args.target):
        # gitのオプションとして解釈されると、ファイルの書き込みなどの外部作用になり得る
        if value is not None and value.startswith("-"):
            print(f"コミットの指定が「-」で始まっています: {value}", file=sys.stderr)
            return 2
    try:
        value = fingerprint(root, args.base, args.target)
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as error:
        detail = getattr(error, "stderr", None)
        reason = (
            detail.decode("utf-8", errors="replace").strip()
            if isinstance(detail, bytes)
            else ""
        ) or str(error)
        print(
            f"指紋を計算できません。基準のコミットとgitの状態を確かめてください: {reason}",
            file=sys.stderr,
        )
        return 2
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
