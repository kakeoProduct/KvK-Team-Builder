"""所属固定の編成と、時間帯ごとの出撃の計算。

所属は時間帯をまたいで変わらない（FRM-010）。各時間帯の出撃メンバーは、所属メンバーのうち
その時間帯に参加しているメンバーと、その時間帯にその隊を応援するメンバーとする（FRM-011、FRM-042）。
遅れて出撃する隊は、出撃開始前の時間帯に出撃しない（FRM-041）。
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
    start_minutes: int | None = None
    """出撃開始時刻（FRM-041）。Noneは戦闘開始から出撃する隊を表す。"""

    @property
    def leader_is_member(self) -> bool:
        """リーダーが所属メンバーにいるか（別枠でないか）を返す。"""

        return self.leader in self.members

    def has_started(self, slot: TimeSlot) -> bool:
        """時間帯が出撃開始以降かを返す。"""

        return self.start_minutes is None or slot.start_minutes >= self.start_minutes


@dataclass(frozen=True, slots=True)
class Support:
    """遅れて出撃する隊のメンバーが、出撃開始前の1つの時間帯にほかの隊を応援すること（FRM-042）。"""

    member: Member
    time_slot: TimeSlot
    team_number: int
    """応援先の隊の番号。"""


@dataclass(frozen=True, slots=True)
class TeamPlan:
    """所属固定の編成。隊、待機、別枠（参加時間未定）を持つ。"""

    teams: tuple[TeamMembership, ...]
    waiting: tuple[Member, ...]
    """上限のためにどの隊にも所属しないメンバー（FRM-033）。"""
    undecided: tuple[Member, ...]
    """【別枠】参加時間未定に置くメンバー（FRM-060）。"""
    supports: tuple[Support, ...] = ()
    """出撃開始前の応援（FRM-042）。応援するメンバーは遅れて出撃する隊に所属する。"""

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
    """所属メンバーのうち、この時間帯に参加しているメンバー。出撃開始前は空とする。"""
    leader_present: bool
    started: bool = True
    """出撃開始以降か（FRM-041）。出撃開始前の時間帯は人数、休止、リーダー不在を判定しない。"""
    supporters: tuple[Member, ...] = ()
    """この時間帯にこの隊を応援するメンバー（FRM-042）。"""

    @property
    def head_count(self) -> int:
        """出撃人数を返す。所属メンバーと応援するメンバーの合計（FRM-011）。"""

        return len(self.members) + len(self.supporters)

    @property
    def sortie_members(self) -> tuple[Member, ...]:
        """出撃するメンバーを返す。所属メンバー、応援するメンバーの順とする。"""

        return (*self.members, *self.supporters)


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
    """隊と時間帯ごとに、所属メンバーのうち参加しているメンバーと応援を出撃として返す。

    参加時間が確定していないメンバーは出撃に数えない。出撃開始前の時間帯は所属メンバーを
    出撃させず、応援するメンバーは編成の応援のとおり応援先に数える。応援が有効かは
    Validatorが確かめる。並びは隊の番号、時間帯の順とする。
    """

    availability_by_member = {item.member: item for item in confirmed}
    result: list[Sortie] = []
    slot_list = tuple(slots)
    for membership in plan.teams:
        for slot in slot_list:
            started = membership.has_started(slot)
            present = (
                tuple(
                    member
                    for member in membership.members
                    if member in availability_by_member
                    and availability_by_member[member].covers(
                        slot.start_minutes, slot.end_minutes
                    )
                )
                if started
                else ()
            )
            supporters = tuple(
                support.member
                for support in plan.supports
                if support.team_number == membership.number
                and support.time_slot == slot
            )
            result.append(
                Sortie(
                    team_number=membership.number,
                    time_slot=slot,
                    members=present,
                    leader_present=membership.leader in present,
                    started=started,
                    supporters=supporters,
                )
            )
    return tuple(result)
