"""チームマスタのJSON Repository。境界は`application.ports.TeamMasterRepository`。"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from kvk_team.team_building.domain.team import TeamLabel
from kvk_team.team_building.domain.team_master import (
    EventTimeSettings,
    StrengthOperator,
    StrengthRelation,
    TeamDefinition,
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
            raw = json.loads(self.path.read_text(encoding="utf-8"))
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

        master = _Fields(raw, "master")
        event = _Fields(master.value("event"), "event")
        event_time = EventTimeSettings(
            start_minutes=event.clock("start_time"),
            end_minutes=event.clock("end_time"),
            slot_minutes=event.integer("slot_minutes"),
        )
        teams = tuple(
            JsonTeamMasterRepository._parse_team(team, index)
            for index, team in enumerate(master.items("teams"), start=1)
        )
        relations = tuple(
            JsonTeamMasterRepository._parse_relation(
                _Fields(relation, f"strength_relations[{index}]")
            )
            for index, relation in enumerate(
                master.items("strength_relations"), start=1
            )
        )
        return TeamMaster(
            schema_version=master.integer("schema_version"),
            event_time=event_time,
            teams=teams,
            strength_relations=relations,
        )

    @staticmethod
    def _parse_team(raw: Any, index: int) -> TeamDefinition:
        """1チーム分のJSONオブジェクトを型を確かめて変換する。"""

        label = _Fields(raw, f"teams[{index}]").choice("label", TeamLabel, "A〜K")
        team = _Fields(raw, label.value)
        team.reject_unknown(_TEAM_KEYS)
        try:
            return TeamDefinition(
                label=label,
                rally_leader=team.string("rally_leader"),
                substitute_leaders=team.string_list("substitute_leaders"),
                role=team.string("role"),
                minimum_members=team.integer("minimum_members"),
                maximum_members=team.integer("maximum_members"),
                vc_required=team.boolean("vc_required"),
                notes=team.string_list("notes"),
            )
        except ValueError as error:
            if str(error).startswith(f"{label.value}: "):
                raise
            raise ValueError(f"{label.value}: {error}") from error

    @staticmethod
    def _parse_relation(relation: "_Fields") -> StrengthRelation:
        """戦力関係のJSONオブジェクトを型を確かめて変換する。"""

        return StrengthRelation(
            stronger=relation.choice("stronger", TeamLabel, "A〜K"),
            weaker=relation.choice("weaker", TeamLabel, "A〜K"),
            operator=relation.choice("operator", StrengthOperator, "「>」または「>=」"),
        )


_Choice = TypeVar("_Choice", bound=Enum)

_TEAM_KEYS = frozenset(
    {
        "label",
        "rally_leader",
        "substitute_leaders",
        "role",
        "minimum_members",
        "maximum_members",
        "vc_required",
        "notes",
    }
)


@dataclass(frozen=True, slots=True)
class _Fields:
    """JSONオブジェクトの項目を型を確かめて取り出す。

    本物のマスタは手で編集するため（ADR 0026）、`str()`や`bool()`で別の値へ変えて読まず、
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

    def boolean(self, key: str) -> bool:
        value = self.value(key)
        if not isinstance(value, bool):
            raise self._invalid(key, "trueまたはfalse", value)
        return value

    def items(self, key: str) -> list[Any]:
        value = self.value(key)
        if not isinstance(value, list):
            raise self._invalid(key, "配列", value)
        return value

    def choice(self, key: str, kind: type[_Choice], allowed: str) -> _Choice:
        value = self.string(key)
        try:
            return kind(value)
        except ValueError as error:
            raise ValueError(
                f"{self.where}: {key}は{allowed}で指定してください"
            ) from error

    def clock(self, key: str) -> int:
        text = self.string(key)
        try:
            return parse_clock(text)
        except ValueError as error:
            raise ValueError(
                f"{self.where}: {key}は「21:00」の形式で指定してください"
            ) from error

    def string_list(self, key: str) -> tuple[str, ...]:
        value = self.raw.get(key, [])
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise self._invalid(key, "文字列の配列", value)
        return tuple(value)


def default_team_master_path() -> Path:
    """同梱する既定JSONマスタのパスを返す。"""

    return Path(__file__).with_name("team_master.json")


def load_default_team_master() -> TeamMaster:
    """既定のJSON Repositoryからチームマスタを読み込む。"""

    return JsonTeamMasterRepository(default_team_master_path()).load()
