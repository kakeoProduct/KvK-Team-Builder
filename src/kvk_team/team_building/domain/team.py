"""チーム編成のドメインモデル。"""

from dataclasses import dataclass
from enum import Enum

from kvk_team.team_building.domain.member import Member


class TeamLabel(str, Enum):
    """戦略上の優先順位で並べた固定チームラベル。"""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"
    I = "I"
    J = "J"
    K = "K"


@dataclass(frozen=True, slots=True)
class Team:
    """1チームに割り当てられたメンバーの不変コレクション。"""

    label: TeamLabel
    members: tuple[Member, ...]

    def member_names(self) -> tuple[str, ...]:
        """表示順でメンバー名を返す。"""

        return tuple(member.name for member in self.members)
