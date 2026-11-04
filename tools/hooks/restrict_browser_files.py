"""Playwright MCPのToolの`filename`を`tmp/playwright-mcp/`の下に限る。

Playwright MCPの`filename`は作業ツリーの内側なら通るため、`browser_evaluate`や、読み取り専用と
宣言された`browser_network_request`でも、Hookの実体、`.claude/settings.json`、`.git/config`を
任意の内容で上書きできる。これらを書き換えると、Git保護と`permissions.deny`が無効になる
（ADR 0032）。上流に名前付きの出力を限る設定はないため、ここで主Sessionを含めて拒否する。
`tool_input`の`_meta.cwd`は`filename`の解決の基準を変えるため、値にかかわらず拒否する。MCPの
仕様では`_meta`は`arguments`の外に置く。Claude Codeでの確認の結果と残る未確認の点は、
ADR 0032の「影響」を見る。

`.claude/settings.json`のmatcherは`mcp__playwright__.*`だけをこのHookへ渡す。`filename`がない
呼び出しは、サーバーが`--output-dir`へ書くため通す。解析できない入力は拒否する。Hookが例外で
終わるとClaude CodeはToolを通すため、例外ではなく拒否として答える。
"""

from __future__ import annotations

import json
import sys
from typing import Any

OUTPUT_DIRECTORY = ("tmp", "playwright-mcp")
DENIED_SEGMENTS = frozenset({"", ".", ".."})


def _is_in_output_directory(filename: str) -> bool:
    """作業ツリーからの相対パスで、出力先の下のファイルを指すかを返す。"""

    # Windowsの区切りとドライブ指定は、OSによって解決が変わるため受け付けない。
    if "\\" in filename or ":" in filename:
        return False
    segments = filename.split("/")
    return (
        tuple(segments[: len(OUTPUT_DIRECTORY)]) == OUTPUT_DIRECTORY
        and len(segments) > len(OUTPUT_DIRECTORY)
        and DENIED_SEGMENTS.isdisjoint(segments)
    )


def _blocked_reason(payload: Any) -> str | None:
    """拒否する理由を返す。許可するときはNoneを返す。"""

    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, dict):
        return "Hook入力を解析できませんでした"
    if "_meta" in tool_input:
        return (
            "`_meta`は`filename`の解決の基準を変えるため、ブラウザのToolへ渡せません"
            "（出力先は`tmp/playwright-mcp/`から始まる相対パスにしてください）"
        )
    if "filename" not in tool_input:
        return None
    filename = tool_input["filename"]
    if isinstance(filename, str) and _is_in_output_directory(filename):
        return None
    # 文字列でない値は深い入れ子で`repr`が例外になり得るため、型の名前だけを示す。
    shown = repr(filename) if isinstance(filename, str) else type(filename).__name__
    return (
        "ブラウザのToolが書くファイルは、`tmp/playwright-mcp/`から始まる相対パスにしてください"
        f"（指定: {shown}）"
    )


def _deny(reason: str) -> None:
    """Tool呼び出しを拒否するJSONを出力する。"""

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"ブラウザの出力先のルールにより拒否しました: {reason}",
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
    except (ValueError, RecursionError):
        _deny("Hook入力を解析できませんでした")
        return 0

    reason = _blocked_reason(payload)
    if reason is not None:
        _deny(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
