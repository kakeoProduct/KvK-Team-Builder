"""所属固定の編成と、時間帯ごとの出撃の計算。

所属は時間帯をまたいで変わらない（FRM-010）。各時間帯の出撃メンバーは、所属メンバーのうち
その時間帯に参加しているメンバーとする（FRM-011）。応援（FRM-042）は運用者の指定とともに
後のPull Requestで加える。
"""

from collections.abc import Iterable
from dataclasses import dataclass

from kvk_team.team_building.domain.availability import ResolvedAvailability
from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.team import SLOT_MINUTES


@dataclass(frozen=True, slots=True)
class TimeSlot:
    """開始時刻を含み終了時刻を含まない時間区間。"""

    start_minutes: int
    end_minutes: int


@dataclass(frozen=True, slots=True)
class TeamMembership:
    """1つの隊のリーダーと所属メンバー。

    `members`は時間帯をまたいで変わらない所属で、参加時間が確定したリーダーを含む。
    参加時間未定のリーダーは別枠に置き、`members`へ含めない（FRM-002、FRM-060）。
    """

    number: int
    leader: Member
    members: tuple[Member, ...]

    @property
    def leader_is_member(self) -> bool:
        """リーダーが所属メンバーにいるか（別枠でないか）を返す。"""

        return self.leader in self.members


@dataclass(frozen=True, slots=True)
class TeamPlan:
    """所属固定の編成。隊、待機、別枠（参加時間未定）を持つ。"""

    teams: tuple[TeamMembership, ...]
    waiting: tuple[Member, ...]
    """上限のためにどの隊にも所属しないメンバー（FRM-033）。"""
    undecided: tuple[Member, ...]
    """【別枠】参加時間未定に置くメンバー（FRM-060）。"""

    def team(self, number: int) -> TeamMembership:
        """番号の隊を返す。"""

        for membership in self.teams:
            if membership.number == number:
                return membership
        raise KeyError(number)


@dataclass(frozen=True, slots=True)
class Sortie:
    """1つの隊の1つの時間帯の出撃。"""

    team_number: int
    time_slot: TimeSlot
    members: tuple[Member, ...]
    leader_present: bool


def time_slots(start_minutes: int, end_minutes: int) -> tuple[TimeSlot, ...]:
    """戦闘時間を30分の時間帯へ等分して返す。"""

    return tuple(
        TimeSlot(start, start + SLOT_MINUTES)
        for start in range(start_minutes, end_minutes, SLOT_MINUTES)
    )


def sorties(
    plan: TeamPlan,
    confirmed: Iterable[ResolvedAvailability],
    slots: Iterable[TimeSlot],
) -> tuple[Sortie, ...]:
    """隊と時間帯ごとに、所属メンバーのうち参加しているメンバーを出撃として返す。

    参加時間が確定していないメンバーは出撃に数えない。並びは隊の番号、時間帯の順とする。
    """

    availability_by_member = {item.member: item for item in confirmed}
    result: list[Sortie] = []
    slot_list = tuple(slots)
    for membership in plan.teams:
        for slot in slot_list:
            present = tuple(
                member
                for member in membership.members
                if member in availability_by_member
                and availability_by_member[member].covers(
                    slot.start_minutes, slot.end_minutes
                )
            )
            result.append(
                Sortie(
                    team_number=membership.number,
                    time_slot=slot,
                    members=present,
                    leader_present=membership.leader in present,
                )
            )
    return tuple(result)
