"""永続化方式に依存しないチームマスタのドメインモデル。"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from kvk_team.team_building.domain.member import MINUTES_PER_HOUR
from kvk_team.team_building.domain.team import TeamLabel


class StrengthOperator(str, Enum):
    """チーム間の戦力比較演算子。"""

    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="


@dataclass(frozen=True, slots=True)
class TeamDefinition:
    """1チームの編成条件と運用情報。"""

    label: TeamLabel
    rally_leader: str
    substitute_leaders: tuple[str, ...]
    role: str
    minimum_members: int
    maximum_members: int
    vc_required: bool
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """チームマスタ内で成立しない人数設定を拒否する。"""

        if not self.rally_leader.strip():
            raise ValueError("集結主を指定してください")
        if self.minimum_members < 1:
            raise ValueError("チームの最低人数は1人以上にしてください")
        if self.maximum_members < self.minimum_members:
            raise ValueError("チームの最大人数は最低人数以上にしてください")


@dataclass(frozen=True, slots=True)
class StrengthRelation:
    """2チーム間で維持する戦力関係。"""

    stronger: TeamLabel
    weaker: TeamLabel
    operator: StrengthOperator


@dataclass(frozen=True, slots=True)
class EventTimeSettings:
    """時間帯別編成に使用するイベント時間設定。"""

    start_minutes: int
    end_minutes: int
    slot_minutes: int

    def __post_init__(self) -> None:
        """時間スロットを正しく分割できない設定を拒否する。"""

        duration = self.end_minutes - self.start_minutes
        if duration <= 0:
            raise ValueError("イベント終了時刻は開始時刻より後にしてください")
        if self.slot_minutes <= 0 or duration % self.slot_minutes:
            raise ValueError("イベント時間を等分できる時間刻みを指定してください")

    @property
    def slot_starts(self) -> tuple[int, ...]:
        """各時間スロットの開始時刻を返す。"""

        return tuple(range(self.start_minutes, self.end_minutes, self.slot_minutes))


@dataclass(frozen=True, slots=True)
class TeamMaster:
    """1つのKvKイベント形式で使用するチームマスタ全体。"""

    schema_version: int
    event_time: EventTimeSettings
    teams: tuple[TeamDefinition, ...]
    strength_relations: tuple[StrengthRelation, ...]

    def __post_init__(self) -> None:
        """重複や参照不整合を含むマスタを拒否する。"""

        if self.schema_version < 1:
            raise ValueError("schema_versionは1以上にしてください")
        labels = tuple(team.label for team in self.teams)
        if len(labels) != len(set(labels)):
            raise ValueError("チームラベルが重複しています")
        if set(labels) != set(TeamLabel):
            raise ValueError("A〜Kの全チームを1件ずつ定義してください")
        for relation in self.strength_relations:
            if relation.stronger not in labels or relation.weaker not in labels:
                raise ValueError("戦力関係が未定義のチームを参照しています")

    @property
    def team_labels(self) -> tuple[TeamLabel, ...]:
        """マスタの定義順でチームラベルを返す。"""

        return tuple(team.label for team in self.teams)

    @property
    def teams_by_label(self) -> Mapping[TeamLabel, TeamDefinition]:
        """チームラベルから定義を参照する不変Mappingを返す。"""

        return MappingProxyType({team.label: team for team in self.teams})

    @property
    def rally_leaders(self) -> Mapping[TeamLabel, str]:
        """チームごとの固定集結主を返す。"""

        return MappingProxyType({team.label: team.rally_leader for team in self.teams})

    @property
    def vc_required_teams(self) -> tuple[TeamLabel, ...]:
        """全時間帯でVCを必須とするチームを返す。"""

        return tuple(team.label for team in self.teams if team.vc_required)


def parse_clock(value: str) -> int:
    """`HH:MM`形式を日跨ぎ対応の分へ変換する。"""

    hour_text, minute_text = value.split(":", maxsplit=1)
    hour = int(hour_text)
    minute = int(minute_text)
    if hour < 0 or minute < 0 or minute >= MINUTES_PER_HOUR:
        raise ValueError(f"不正な時刻です: {value}")
    return hour * MINUTES_PER_HOUR + minute
