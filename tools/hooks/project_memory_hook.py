"""Claude CodeのSession Hookから共有記憶の開始と記録漏れ確認を行う。

`session-start`は開始時のGit状態を保存し、session_idをAgentのContextへ渡す。
`stop`は未記録の変更が残る場合に一度だけ停止を止め、`finish`の実行を促す。
SessionがRepository内のSession用worktreeへ移った場合は、Payloadの`cwd`から
そのworktreeの共有記憶Scriptを使う。
このHookは補助的な仕組みであり、失敗しても作業自体は止めない。標準ライブラリだけで
動作させ、共有記憶ScriptはRepositoryの仮想環境のPythonで実行する。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORY_SCRIPT_PATH = Path(
    ".agents", "skills", "maintain-project-memory", "scripts", "session_memory.py"
)
# Session用worktreeを置くRepository内のDirectory。
WORKTREE_PARENTS = (
    PROJECT_ROOT / ".worktrees",
    PROJECT_ROOT / ".claude" / "worktrees",
)
# Windowsと共有するWorkspaceでは両方のvenvが見えるため、実行中のOSに合う方だけを使う。
VIRTUAL_ENVIRONMENT_PYTHON = (
    PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if os.name == "nt"
    else PROJECT_ROOT / ".venv" / "bin" / "python"
)
SCRIPT_TIMEOUT_SECONDS = 60


class HookError(RuntimeError):
    """Hookの処理を続けられない理由。"""


def _python_executable() -> str:
    """共有記憶Scriptの依存関係を持つPythonを返す。"""

    if VIRTUAL_ENVIRONMENT_PYTHON.is_file():
        return str(VIRTUAL_ENVIRONMENT_PYTHON)
    return sys.executable


def _working_root(payload: dict[str, Any]) -> Path:
    """Sessionが作業している作業ツリーのRootを返す。

    Session用worktreeの内側にある`cwd`だけを採用し、それ以外は元の作業ツリーとする。
    """

    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return PROJECT_ROOT
    try:
        current = Path(cwd).resolve()
    except OSError:
        return PROJECT_ROOT
    for parent in WORKTREE_PARENTS:
        try:
            relative = current.relative_to(parent.resolve())
        except ValueError:
            continue
        if relative.parts:
            root = parent / relative.parts[0]
            if (root / MEMORY_SCRIPT_PATH).is_file():
                return root
    return PROJECT_ROOT


def _run_memory_script(root: Path, *arguments: str) -> dict[str, Any]:
    """共有記憶Scriptを実行し、JSON結果を返す。"""

    try:
        completed = subprocess.run(
            [_python_executable(), str(root / MEMORY_SCRIPT_PATH), *arguments],
            cwd=root,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            check=False,
            timeout=SCRIPT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise HookError(f"共有記憶Scriptを実行できません: {error}") from error
    stdout = completed.stdout.decode("utf-8", errors="replace")
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise HookError(stderr or "共有記憶Scriptが失敗しました。")
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise HookError("共有記憶Scriptの出力を解析できません。") from error
    if not isinstance(result, dict):
        raise HookError("共有記憶Scriptの出力が不正です。")
    return result


def _read_payload() -> dict[str, Any]:
    """標準入力のHook PayloadをUTF-8のJSONとして読む。"""

    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HookError("Hook入力を解析できません。") from error
    if not isinstance(payload, dict):
        raise HookError("Hook入力が不正です。")
    return payload


def _session_id(payload: dict[str, Any]) -> str:
    """Hook Payloadからsession_idを取得する。"""

    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise HookError("Hook入力にsession_idがありません。")
    return session_id


def _emit(value: dict[str, Any]) -> None:
    """既定コードページへ依存しないJSONを標準出力へ書く。"""

    print(json.dumps(value, ensure_ascii=True))


def _session_start(payload: dict[str, Any]) -> None:
    """開始時状態を保存し、AgentへContextを渡す。"""

    session_id = _session_id(payload)
    result = _run_memory_script(
        _working_root(payload),
        "start",
        "--session-id",
        session_id,
        "--keep-existing",
    )
    preexisting = result.get("preexisting_paths") or []
    context = (
        "共有記憶の開始状態はHookが保存済みです。"
        f"`$maintain-project-memory`のsession_idは`{session_id}`を使い、"
        "startを再実行しないでください。"
        f"開始前から存在する利用者の差分は{len(preexisting)}件で、記録対象外です。"
        "変更作業の完了前に、このsession_idでfinishを実行してください。"
    )
    if result.get("use_separate_worktree") is True:
        others = result.get("other_active_sessions") or []
        context += (
            f"この作業ツリーは別Session（{len(others)}件）が使用中です。"
            "Repositoryを変更する場合は、`$implement`の手順でSession用worktreeへ移り、"
            f"この作業ツリーのsession_id`{session_id}`をdiscardしてから、"
            "移動先のworktreeで同じsession_idのstartを実行してください。"
            "読み取りだけの作業なら移動は不要です。"
        )
    _emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            }
        }
    )


def _stop(payload: dict[str, Any]) -> None:
    """未記録の変更があれば一度だけ停止を止める。"""

    if payload.get("stop_hook_active") is True:
        return
    session_id = _session_id(payload)
    result = _run_memory_script(
        _working_root(payload), "status", "--session-id", session_id, "--mark-reminded"
    )
    pending_paths = result.get("pending_paths") or []
    if not result.get("started") or not pending_paths or result.get("reminded"):
        return
    listed = "、".join(str(path) for path in pending_paths[:10])
    if len(pending_paths) > 10:
        listed += f" ほか{len(pending_paths) - 10}件"
    reason = (
        f"共有記憶へ未記録のRepository変更があります: {listed}。"
        "変更作業が完了しているなら、`$maintain-project-memory`の手順で"
        f"`finish --session-id {session_id}`を実行してから最終報告してください。"
        "作業途中で利用者の判断を待つ場合は、その旨を伝えて停止して構いません。"
        "この確認は1 Sessionにつき1回だけ行います。"
    )
    _emit({"decision": "block", "reason": reason})


def _use_utf8_output() -> None:
    """Windows CIなど非UTF-8のConsoleでも日本語の出力で失敗しないようにする。"""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def create_argument_parser() -> argparse.ArgumentParser:
    """Hook Scriptの引数Parserを生成する。"""

    parser = argparse.ArgumentParser(description="共有記憶のSession Hookです。")
    parser.add_argument("event", choices=("session-start", "stop"))
    return parser


def main(argv: list[str] | None = None) -> int:
    """指定されたHook Eventを処理する。失敗しても作業を止めない。"""

    _use_utf8_output()
    args = create_argument_parser().parse_args(argv)
    handler = _session_start if args.event == "session-start" else _stop
    try:
        handler(_read_payload())
    except HookError as error:
        print(f"共有記憶Hookを省略しました: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
