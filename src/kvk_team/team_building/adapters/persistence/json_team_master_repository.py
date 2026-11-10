"""チームマスタのJSON Repository。境界は`application.ports.TeamMasterRepository`。"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kvk_team.team_building.domain.team_master import (
    TEAM_MASTER_SCHEMA_VERSION,
    EventTimeSettings,
    TeamMaster,
    parse_clock,
)


class TeamMasterLoadError(ValueError):
    """チームマスタを安全に読み込めない場合に送出する。"""


@dataclass(frozen=True, slots=True)
class JsonTeamMasterRepository:
    """JSONファイルからチームマスタを構築するRepository。"""

    path: Path

    def load(self) -> TeamMaster:
        """JSONを読み込み、検証済みのチームマスタを返す。"""

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
            return self._parse_master(raw)
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise TeamMasterLoadError(
                f"チームマスタを読み込めません: {self.path}: {error}"
            ) from error

    @staticmethod
    def _parse_master(raw: dict[str, Any]) -> TeamMaster:
        """JSONオブジェクトを型付きマスタへ変換する。"""

        master = JsonFields(raw, "master")
        version = master.integer("schema_version")
        if version != TEAM_MASTER_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version {version}の形は読めません。"
                f"schema_version {TEAM_MASTER_SCHEMA_VERSION}へ移してください。"
                "隊ごとの集結主（teams）、戦力関係（strength_relations）、"
                "時間刻み（event.slot_minutes）はなくなり、第4隊以降の上限を`member_cap`に"
                "書きます。リーダー一覧はイベントのフォルダのsettings.jsonの`leaders`へ書きます"
                "（ADR 0034）"
            )
        master.reject_unknown(_MASTER_KEYS)
        event = JsonFields(master.value("event"), "event")
        event.reject_unknown(_EVENT_KEYS)
        event_time = EventTimeSettings(
            start_minutes=event.clock("start_time"),
            end_minutes=event.clock("end_time"),
        )
        return TeamMaster(
            schema_version=version,
            event_time=event_time,
            member_cap=master.integer("member_cap"),
        )


_MASTER_KEYS = frozenset({"schema_version", "event", "member_cap"})
_EVENT_KEYS = frozenset({"start_time", "end_time"})
"""時間帯の長さは固定値の30分で、`slot_minutes`は書かない（ADR 0034）。"""


@dataclass(frozen=True, slots=True)
class JsonFields:
    """JSONオブジェクトの項目を型を確かめて取り出す。

    本物の設定は手で編集するため（ADR 0026）、`str()`や`bool()`で別の値へ変えて読まず、
    書き間違えた項目を黙って読み飛ばさない。誤りは、どこの項目かを示す例外にする。
    本物の名前が不具合報告へ漏れないよう、値そのものではなく型名だけを示す。
    """

    raw: dict[str, Any]
    where: str

    def _invalid(self, key: str, expected: str, value: object) -> TypeError:
        return TypeError(
            f"{self.where}: {key}は{expected}で指定してください"
            f"（{type(value).__name__}が書かれています）"
        )

    def value(self, key: str) -> Any:
        if not isinstance(self.raw, dict):
            raise TypeError(f"{self.where}はオブジェクトで指定してください")
        if key not in self.raw:
            raise ValueError(f"{self.where}: {key}がありません")
        return self.raw[key]

    def reject_unknown(self, allowed: frozenset[str]) -> None:
        if not isinstance(self.raw, dict):
            raise TypeError(f"{self.where}はオブジェクトで指定してください")
        unknown = sorted(set(self.raw) - allowed)
        if unknown:
            raise ValueError(f"{self.where}: 未知の項目{'、'.join(unknown)}があります")

    def string(self, key: str) -> str:
        value = self.value(key)
        if not isinstance(value, str):
            raise self._invalid(key, "文字列", value)
        return value

    def integer(self, key: str) -> int:
        value = self.value(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise self._invalid(key, "整数", value)
        return value

    def items(self, key: str) -> list[Any]:
        value = self.value(key)
        if not isinstance(value, list):
            raise self._invalid(key, "配列", value)
        return value

    def clock(self, key: str) -> int:
        text = self.string(key)
        try:
            return parse_clock(text)
        except ValueError as error:
            raise ValueError(
                f"{self.where}: {key}は「21:00」の形式で指定してください"
            ) from error


def default_team_master_path() -> Path:
    """同梱する既定JSONマスタのパスを返す。"""

    return Path(__file__).with_name("team_master.json")


def load_default_team_master() -> TeamMaster:
    """既定のJSON Repositoryからチームマスタを読み込む。"""

    return JsonTeamMasterRepository(default_team_master_path()).load()
