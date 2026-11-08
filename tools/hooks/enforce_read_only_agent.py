"""読み取り専用のReview AgentのTool呼び出しを、権限モードにかかわらず制限する。

Claude Codeでは親Sessionが`auto`、`acceptEdits`、`bypassPermissions`のとき、Subagentの
`permissionMode: plan`が無視される。PreToolUse Hookの拒否は権限モードより先に評価される
ため、`.claude/settings.json`へ登録して`plan`相当の制限を強制する。Subagent定義の
Frontmatterへ書いたHookは、この環境では発火しなかった。

Hook入力の`agent_type`が、正本の`.codex/agents/`で`sandbox_mode = "read-only"`と宣言した
Agentのときだけ制限する。`agent_type`のない主Sessionと、読み取り専用と宣言していない他のAgentの
Tool呼び出しは通す。定義ファイルのないAgentは他のAgentとして通す。定義ファイルを解析できないAgentは
読み取り専用として制限し、`null`以外の文字列でない`agent_type`は対象を確かめられないため拒否する。
解析できないHook入力は主Sessionを含めて拒否する。

`.claude/settings.json`のmatcherは、書き込み得るTool（Bash、PowerShell、Monitor、編集Tool、
Agent、MCP）だけをこのHookへ渡す。読み取りToolと内部Toolでは起動しないため、Claude Codeが
内部Toolを増やしても結果の返却を妨げない。制限対象のAgentでは、届いたToolを拒否する。例外は
Bashの`python tools/review_query.py`の呼び出しだけで、引数を「安全な文字だけの語」か「単一引用符で
囲んだ文字列」に限る閉じた文法で確かめる。この形ではShellの展開も区切りも起きないため、コマンドの
意味は解釈しない。GitとpytestのOptionの意味は、そのScriptへ閉じ込める（ADR 0033）。
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_DEFINITION_DIRECTORY = PROJECT_ROOT / ".codex" / "agents"
# 語はShellが解釈しない文字だけで作る。`~`は語頭と、`=`か`:`の直後で展開される
# （bashは`a=~/x`の形の引数も展開する）ため、それ以外の位置に限る。
REVIEW_QUERY_COMMAND = re.compile(
    r"python tools/review_query\.py"
    r"(?: (?:[A-Za-z0-9_./:=@,+%^-](?:[A-Za-z0-9_./:=@,+%^-]|(?<![=:])~)*"
    r"|'[^'\r\n]*'))+"
)


def _is_read_only_agent(agent_type: str) -> bool:
    """正本のAgent定義が読み取り専用を宣言しているかを返す。"""

    # Agent名をパスとして解釈させないよう、定義ファイル名と完全一致する場合だけ読む。
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", agent_type):
        return False
    path = AGENT_DEFINITION_DIRECTORY / f"{agent_type}.toml"
    try:
        if not path.is_file():
            return False
        with path.open("rb") as source:
            definition = tomllib.load(source)
    except (OSError, ValueError, RecursionError):
        # 読み取り専用と宣言されたか確かめられないAgentは安全側で制限する。
        return True
    return definition.get("sandbox_mode") == "read-only"


def _blocked_reason(payload: Any) -> str | None:
    """拒否する理由を返す。許可する場合はNoneを返す。"""

    if not isinstance(payload, dict) or payload.get("hook_event_name") != "PreToolUse":
        return "Hook入力を解析できませんでした"
    agent_type = payload.get("agent_type")
    if agent_type is None:
        return None
    if not isinstance(agent_type, str):
        return "Agentを確認できませんでした"
    if not _is_read_only_agent(agent_type):
        return None
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str):
        return "Tool名を確認できませんでした"
    if tool_name != "Bash":
        return f"{tool_name}は読み取り専用のAgentで使用できません"
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if isinstance(command, str) and REVIEW_QUERY_COMMAND.fullmatch(command):
        return None
    return (
        "Bashで実行できるのは`python tools/review_query.py`だけです。"
        "引数は空白1つで区切り、英数字と`_./:=@,+%~^-`以外を含む値（日本語を含む）と、"
        "語頭か`=`、`:`の直後に`~`がある値は単一引用符で囲んでください"
    )


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
    # 深い入れ子のRecursionErrorと巨大な整数のValueErrorも含め、例外で判定なしに終わらせない。
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
