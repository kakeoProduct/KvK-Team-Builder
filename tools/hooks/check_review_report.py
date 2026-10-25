"""Review Agentの結果が必須の見出しと列を含むかを、返す前に検査する。

Claude CodeとCodexのSubagentStop Hookから起動する。主Sessionはレビュー結果を
`Must`、`Should`、`Nice`、`未確定`に分けて統合するため、見出しが欠けた結果を受け取ると、
指摘なしと書き漏れを区別できない。欠けていれば理由を返してSubagentに書き直させる。

Claude CodeのSubagentは、最終報告を本文ではなく`SubagentHandback`の呼び出しで返すことがある。
この場合は`last_assistant_message`に報告がないため、`agent_transcript_path`の記録から最後の
`SubagentHandback`の報告を読む。どちらからも報告を取り出せなければ、書き漏れと区別できない
ため止めない。

書き直しは1回までとし、Hook入力の`stop_hook_active`が真なら検査せずに通す。結果の形式を
整える補助的な検査のため、解析できない入力や対象外のAgentでは作業を止めない。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Agentごとに、結果が含むべき行。各Agentの指示（.codex/agents/）と同じ表記にする。
REVIEW_REPORT_HEADINGS = ("## Must", "## Should", "## Nice", "## 未確定")
EVIDENCE_TABLE_COLUMNS = ("主張", "判定", "出典URL", "確認日", "必要な訂正")
CODE_REVIEW_AGENTS = frozenset(
    {
        "kvk-architecture-reviewer",
        "kvk-domain-reviewer",
        "kvk-requirements-reviewer",
        "kvk-test-reviewer",
    }
)
EVIDENCE_REVIEW_AGENT = "evidence-reviewer"
TABLE_SEPARATOR = re.compile(r"\s*\|\s*")
# Claude CodeのSubagentが最終報告を返すTool。
HANDBACK_TOOL = "SubagentHandback"


def _has_heading(lines: list[str], heading: str) -> bool:
    """見出しの行が、`## Must（承認前に必須）`のような補足付きでも存在するかを返す。"""

    return any(line.startswith(heading) for line in lines)


def _has_evidence_table(lines: list[str]) -> bool:
    """判定表の見出し行が、決めた列をこの順に含むかを返す。"""

    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [cell for cell in TABLE_SEPARATOR.split(line.strip("| ")) if cell]
        if tuple(cells[: len(EVIDENCE_TABLE_COLUMNS)]) == EVIDENCE_TABLE_COLUMNS:
            return True
    return False


def _missing_parts(agent_type: str, message: str) -> list[str]:
    """結果に欠けている見出しまたは列を返す。対象外のAgentでは空を返す。"""

    lines = [line.strip() for line in message.splitlines()]
    if agent_type in CODE_REVIEW_AGENTS:
        return [
            heading
            for heading in REVIEW_REPORT_HEADINGS
            if not _has_heading(lines, heading)
        ]
    if agent_type == EVIDENCE_REVIEW_AGENT and not _has_evidence_table(lines):
        return ["| " + " | ".join(EVIDENCE_TABLE_COLUMNS) + " |"]
    return []


def _handback_report(entry: Any) -> str | None:
    """記録の1行が最終報告のTool呼び出しなら、その報告を返す。"""

    if not isinstance(entry, dict) or entry.get("type") != "assistant":
        return None
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return None
    for item in reversed(content):
        if (
            isinstance(item, dict)
            and item.get("type") == "tool_use"
            and item.get("name") == HANDBACK_TOOL
            and isinstance(item.get("input"), dict)
        ):
            report = item["input"].get("message")
            if isinstance(report, str) and report.strip():
                return report
    return None


def _transcript_report(transcript_path: Any) -> str | None:
    """Subagentの記録から、最後に最終報告のToolで返した報告を返す。"""

    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    try:
        lines = Path(transcript_path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for line in reversed(lines):
        try:
            report = _handback_report(json.loads(line))
        except json.JSONDecodeError:
            continue
        if report is not None:
            return report
    return None


def _block_reason(payload: Any) -> str | None:
    """書き直しを求める理由を返す。そのまま返させる場合はNoneを返す。"""

    if not isinstance(payload, dict) or payload.get("stop_hook_active") is True:
        return None
    agent_type = payload.get("agent_type")
    if not isinstance(agent_type, str) or agent_type not in (
        CODE_REVIEW_AGENTS | {EVIDENCE_REVIEW_AGENT}
    ):
        return None
    message = payload.get("last_assistant_message")
    reports: list[str] = []
    if isinstance(message, str) and message.strip():
        # 本文が形式を満たせば、大きくなり得る記録を読まずに返す。
        if not _missing_parts(agent_type, message):
            return None
        reports.append(message)
    transcript_report = _transcript_report(payload.get("agent_transcript_path"))
    if transcript_report is not None:
        if not _missing_parts(agent_type, transcript_report):
            return None
        reports.append(transcript_report)
    if not reports:
        return None
    # 最終報告のToolで返した報告があれば、それを不足の説明に使う。
    missing = _missing_parts(agent_type, reports[-1])
    return (
        "結果に次の行がありません: "
        + "、".join(missing)
        + "。指摘の内容は変えずに、欠けた行を加えた結果全体を返してください。"
        "該当がない見出しには「なし」と書いてください。"
    )


def _use_utf8_output() -> None:
    """Windows CIなど非UTF-8のConsoleでも日本語の出力で失敗しないようにする。"""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    """標準入力のSubagentStop Payloadを検査する。"""

    _use_utf8_output()
    argparse.ArgumentParser(
        description="Review Agentの結果が必須の見出しと列を含むかを検査する。"
    ).parse_args(argv)
    # Windowsの既定コードページへ依存せず、HookのJSONをUTF-8として読む。
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        print(f"レビュー結果を検査できませんでした: {error}", file=sys.stderr)
        return 0

    reason = _block_reason(payload)
    if reason is not None:
        # 既定コードページへ依存しないよう、非ASCII文字をエスケープして出力する。
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
