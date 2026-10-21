"""性質テストで共有する、必須条件を満たす編成のHypothesis戦略。

戦略は既定のJSONチームマスタを前提に、全時間帯で必須条件を満たす参加者と配置を
構成的に作る。D〜Kの8人未満と集結主の到着待ちは警告のため、意図的に含める。
前提は`master_assumption_errors()`にまとめ、チームマスタの変更で崩れたことを
Validatorの退行と区別して報告する。
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from hypothesis import assume
from hypothesis import strategies as st

from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.team_building.domain.member import KVK_START_MINUTES, Member, Tier
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.schedule import (
    DynamicTeamPlan,
    SlotAssignment,
    TimeSlot,
)
from kvk_team.team_building.domain.team import TeamLabel
from kvk_team.team_building.domain.team_master import StrengthOperator

RULES: KvKRules = default_rules()
MASTER = RULES.team_master
SLOT_STARTS = MASTER.event_time.slot_starts
SLOT_MINUTES = MASTER.event_time.slot_minutes
FIXED_TEAMS = tuple(team.label for team in MASTER.teams if team.vc_required)
"""VC必須で人数固定のチーム。戦力関係もこの順に並ぶ前提とする。"""
FLEXIBLE_TEAMS = tuple(
    label for label in MASTER.team_labels if label not in FIXED_TEAMS
)
FIXED_TEAM_SIZE = MASTER.teams_by_label[FIXED_TEAMS[0]].maximum_members

Roster = dict[int, dict[TeamLabel, list[Member]]]
"""時間帯の開始時刻ごとの、チーム別メンバー一覧。"""


def master_assumption_errors() -> list[str]:
    """生成戦略が前提とするチームマスタの形と、実際のチームマスタの違いを返す。"""

    errors: list[str] = []
    if FIXED_TEAMS != (TeamLabel.A, TeamLabel.B, TeamLabel.C):
        errors.append(f"VC必須のチームがA〜Cではありません: {FIXED_TEAMS}")
    for label in FIXED_TEAMS:
        definition = MASTER.teams_by_label[label]
        if definition.minimum_members != definition.maximum_members:
            errors.append(f"{label.value}の人数が固定ではありません")
        if definition.maximum_members != FIXED_TEAM_SIZE:
            errors.append(f"{label.value}の固定人数がほかのA〜Cと異なります")
    for label in FLEXIBLE_TEAMS:
        definition = MASTER.teams_by_label[label]
        if definition.minimum_members >= definition.maximum_members:
            errors.append(f"{label.value}の不足が警告になる人数幅がありません")
    relations = tuple(
        (relation.stronger, relation.weaker, relation.operator)
        for relation in MASTER.strength_relations
    )
    expected_relations = (
        (TeamLabel.A, TeamLabel.B, StrengthOperator.GREATER_THAN),
        (TeamLabel.B, TeamLabel.C, StrengthOperator.GREATER_THAN_OR_EQUAL),
    )
    if relations != expected_relations:
        errors.append(f"戦力関係がA > B >= Cではありません: {relations}")
    return errors


def team_power(members: list[Member]) -> int:
    """メンバー一覧の戦力合計を返す。"""

    return sum(RULES.tier_power[member.tier] for member in members)


@dataclass(frozen=True, slots=True)
class Scenario:
    """入力参加者と、その参加者で必須条件を満たす全時間帯の配置。"""

    members: tuple[Member, ...]
    standby: tuple[Member, ...]
    roster: Mapping[int, Mapping[TeamLabel, tuple[Member, ...]]]

    @property
    def source_members(self) -> list[Member]:
        """Validatorへ渡す入力参加者を返す。"""

        return [*self.members, *self.standby]

    def copy_roster(self) -> Roster:
        """変更用に配置の複製を返す。"""

        return {
            start: {label: list(members) for label, members in teams.items()}
            for start, teams in self.roster.items()
        }

    def plan(self, roster: Roster | None = None) -> DynamicTeamPlan:
        """配置を動的編成へ変換する。"""

        source = roster if roster is not None else self.copy_roster()
        assignments = tuple(
            SlotAssignment(
                team_label=label,
                time_slot=TimeSlot(start, start + SLOT_MINUTES),
                members=tuple(source[start][label]),
            )
            for start in SLOT_STARTS
            for label in MASTER.team_labels
        )
        return DynamicTeamPlan(assignments=assignments, standby_members=self.standby)


tiers = st.sampled_from(tuple(Tier))


@st.composite
def time_windows(draw: st.DrawFn) -> tuple[int, int]:
    """時間帯の境界にそろえない場合も含む、参加開始と終了の分を返す。"""

    event = MASTER.event_time
    start = draw(
        st.sampled_from(SLOT_STARTS)
        | st.integers(min_value=event.start_minutes, max_value=event.end_minutes - 1)
    )
    end = draw(
        st.sampled_from(
            [slot + SLOT_MINUTES for slot in SLOT_STARTS if slot + SLOT_MINUTES > start]
        )
        | st.integers(min_value=start + 1, max_value=event.end_minutes)
    )
    return start, end


def _member(
    name: str,
    tier: Tier,
    has_vc: bool,
    window: tuple[int, int] | None = None,
) -> Member:
    """全時間帯または指定時間だけ参加するメンバーを作る。"""

    if window is None:
        return Member(name=name, alliance="検証同盟", tier=tier, has_vc=has_vc)
    start, end = window
    return Member(
        name=name,
        alliance="検証同盟",
        tier=tier,
        has_vc=has_vc,
        starts_at_21=start == KVK_START_MINUTES,
        start_time_minutes=start,
        end_time_minutes=end,
    )


def _covers(member: Member, slot_start: int) -> bool:
    """生成したメンバーの参加時間が時間帯全体を含むかを返す。"""

    start = member.start_time_minutes
    end = member.end_time_minutes
    if start is None:
        return False
    return start <= slot_start and (end is None or end >= slot_start + SLOT_MINUTES)


class PowerTie(Enum):
    """A〜Cの戦力を意図的に同値にする組み合わせ。"""

    A_EQUALS_B = "A=B"
    """`A > B`を破る。ほかの必須条件は満たす。"""
    B_EQUALS_C = "B=C"
    """`B >= C`の境界で、必須条件を満たす。"""


@st.composite
def scenarios(draw: st.DrawFn, power_tie: PowerTie | None = None) -> Scenario:
    """全時間帯で必須条件を満たす参加者と配置を生成する。

    `power_tie`を指定すると、A〜Cの戦力だけを指定の同値にする。
    """

    # A〜Cは全時間帯に参加するVC可能な8人ずつとし、戦力の高い順に配る。
    fixed_tiers = sorted(
        draw(
            st.lists(
                tiers,
                min_size=FIXED_TEAM_SIZE * len(FIXED_TEAMS),
                max_size=FIXED_TEAM_SIZE * len(FIXED_TEAMS),
            )
        ),
        key=lambda tier: RULES.tier_power[tier],
        reverse=True,
    )
    chunks = [
        fixed_tiers[index * FIXED_TEAM_SIZE : (index + 1) * FIXED_TEAM_SIZE]
        for index in range(len(FIXED_TEAMS))
    ]
    if power_tie is PowerTie.A_EQUALS_B:
        chunks[1] = chunks[0]
    elif power_tie is PowerTie.B_EQUALS_C:
        chunks[2] = chunks[1]
    fixed_members: dict[TeamLabel, list[Member]] = {}
    for label, chunk in zip(FIXED_TEAMS, chunks, strict=True):
        definition = MASTER.teams_by_label[label]
        names = [definition.rally_leader] + [
            f"{label.value}参加者{index}" for index in range(1, FIXED_TEAM_SIZE)
        ]
        fixed_members[label] = [
            _member(name, tier, has_vc=True)
            for name, tier in zip(names, chunk, strict=True)
        ]
    if power_tie is not PowerTie.A_EQUALS_B:
        assume(
            team_power(fixed_members[TeamLabel.A])
            > team_power(fixed_members[TeamLabel.B])
        )

    # D〜Kは0人から最大人数までで、集結主の不在、途中参加、途中離脱、VC不可を含める。
    flexible_members: dict[TeamLabel, list[Member]] = {}
    for label in FLEXIBLE_TEAMS:
        definition = MASTER.teams_by_label[label]
        names: list[str] = []
        if draw(st.booleans()):
            names.append(definition.rally_leader)
        names.extend(
            leader for leader in definition.substitute_leaders if draw(st.booleans())
        )
        other_count = draw(
            st.integers(
                min_value=0,
                max_value=definition.maximum_members - len(names),
            )
        )
        names.extend(f"{label.value}参加者{index}" for index in range(other_count))
        flexible_members[label] = [
            _member(
                name,
                draw(tiers),
                draw(st.booleans()),
                draw(st.none() | time_windows()),
            )
            for name in names
        ]

    standby = tuple(
        Member(
            name=f"待機参加者{index}",
            alliance="検証同盟",
            tier=draw(tiers),
            has_vc=draw(st.booleans()),
            starts_at_21=False,
        )
        for index in range(draw(st.integers(min_value=0, max_value=3)))
    )

    members_by_team = {**fixed_members, **flexible_members}
    roster = {
        start: {
            label: tuple(
                member for member in members_by_team[label] if _covers(member, start)
            )
            for label in MASTER.team_labels
        }
        for start in SLOT_STARTS
    }
    members = tuple(
        member for label in MASTER.team_labels for member in members_by_team[label]
    )
    return Scenario(members=members, standby=standby, roster=roster)
