"""開発Toolが非UTF-8のConsoleでも日本語を出力できることを検証する。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL_DIRECTORY = PROJECT_ROOT / "tools"


def _tool_scripts() -> list[str]:
    """直接実行される`tools/`配下のScriptを列挙する。"""

    return sorted(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in TOOL_DIRECTORY.rglob("*.py")
        if "__pycache__" not in path.parts
        and 'if __name__ == "__main__":' in path.read_text(encoding="utf-8")
    )


def test_tool_scripts_are_discovered() -> None:
    """新しいScriptを追加しても文字コード検査の対象から漏れない。"""

    assert {
        "tools/check.py",
        "tools/preview_output.py",
        "tools/sync_agent_config.py",
        "tools/hooks/block_dangerous_git.py",
        "tools/hooks/project_memory_hook.py",
    } <= set(_tool_scripts())


@pytest.mark.parametrize(
    "arguments",
    [
        ("tools/sync_agent_config.py", "--check"),
        *((script, "--help") for script in _tool_scripts()),
    ],
)
def test_tools_print_japanese_on_cp1252_console(arguments: tuple[str, ...]) -> None:
    """Windows CIと同じcp1252出力でもUnicodeEncodeErrorで失敗しない。"""

    # インストール済みのパッケージではなく、このチェックアウトのsrcを読み込ませる。
    # 複数のworktreeが同じPython環境を共有しても、検査対象のコードが入れ替わらない
    environment = {
        **os.environ,
        "PYTHONIOENCODING": "cp1252",
        "PYTHONUTF8": "0",
        "PYTHONPATH": str(PROJECT_ROOT / "src"),
    }
    completed = subprocess.run(
        [sys.executable, *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert "UnicodeEncodeError" not in completed.stderr.decode("utf-8", "replace")
    assert completed.stdout.decode("utf-8")
