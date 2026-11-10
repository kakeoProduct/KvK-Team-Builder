"""性質テストで共有する、必須条件を満たす所属固定の編成のHypothesis戦略。

戦略は既定のチームマスタ（戦闘時間と上限）と固定値（上位隊3隊×8人、延長境界時刻）を前提に、
全時間帯で必須条件を満たす参加者、運用者の指定、所属を構成的に作る。第4隊以降の8人未満、
リーダー不在、延長境界時刻以降の休止は警告のため、意図的に含める。前提は
`master_assumption_errors()`にまとめ、チームマスタの変更で崩れたことをValidatorの退行と
区別して報告する。
"""

from dataclasses import dataclass, replace
from enum import Enum

from hypothesis import assume
from hypothesis import strategies as st

from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.team_building.domain.member import KVK_START_MINUTES, Member, Tier
from kvk_team.team_building.domain.plan import TeamMembership, TeamPlan
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.specification import (
    MemberRef,
    OperatorSpecification,
)
from kvk_team.team_building.domain.team import (
    EXTENSION_BOUNDARY_MINUTES,
    TOP_TEAM_COUNT,
    TOP_TEAM_SIZE,
)

RULES: KvKRules = default_rules()
EVENT = RULES.team_master.event_time
SLOT_STARTS = EVENT.slot_starts
SLOT_MINUTES = EVENT.slot_minutes
MEMBER_CAP = RULES.member_cap
ALLIANCE = "検証同盟"
MAXIMUM_FLEXIBLE_TEAMS = 4
"""第4隊以降の数の上限。Optimizerの性質テストの実行時間を抑える。"""


def master_assumption_errors() -> list[str]:
    """生成戦略が前提とするチームマスタの形と、実際のチームマスタの違いを返す。"""

    errors: list[str] = []
    if EVENT.start_minutes >= EXTENSION_BOUNDARY_MINUTES:
        errors.append("戦闘開始が延長境界時刻より前ではありません")
    if EVENT.end_minutes <= EXTENSION_BOUNDARY_MINUTES:
        errors.append(
            "戦闘終了が延長境界時刻より後ではなく、延長境界時刻以降を生成できません"
        )
    if EVENT.start_minutes != KVK_START_MINUTES:
        errors.append("戦闘開始が参加者の既定の開始時刻と違います")
    if MEMBER_CAP < 2:
        errors.append("上限が小さすぎ、リーダー以外の所属を生成できません")
    return errors


def team_power(members: tuple[Member, ...] | list[Member]) -> int:
    """メンバー一覧の戦力合計を返す。"""

    return sum(RULES.tier_power[member.tier] for member in members)


def covers(member: Member, slot_start: int) -> bool:
    """生成したメンバーの参加時間が時間帯全体を含むかを返す。"""

    start = member.start_time_minutes
    end = member.end_time_minutes
    if start is None:
        return False
    return start <= slot_start and (end is None or end >= slot_start + SLOT_MINUTES)


@dataclass(frozen=True, slots=True)
class Scenario:
    """入力参加者、運用者の指定、その参加者で必須条件を満たす所属。"""

    teams: tuple[tuple[Member, ...], ...]
    """隊の番号順の所属メンバー。参加時間が確定したリーダーを先頭に含む。"""
    leaders: tuple[Member, ...]
    waiting: tuple[Member, ...]
    undecided: tuple[Member, ...]

    @property
    def source_members(self) -> list[Member]:
        """Validatorへ渡す入力参加者を返す。"""

        members = [member for team in self.teams for member in team]
        return [*members, *self.waiting, *self.undecided]

    @property
    def specification(self) -> OperatorSpecification:
        """リーダー一覧の運用者の指定を返す。"""

        return OperatorSpecification(
            leaders=tuple(
                MemberRef(leader.name, leader.alliance) for leader in self.leaders
            )
        )

    def copy_teams(self) -> list[list[Member]]:
        """変更用に所属の複製を返す。"""

        return [list(team) for team in self.teams]

    def plan(
        self,
        teams: list[list[Member]] | None = None,
        waiting: list[Member] | None = None,
        undecided: list[Member] | None = None,
    ) -> TeamPlan:
        """所属を編成へ変換する。省略した部分は生成した値を使う。"""

        source = teams if teams is not None else self.copy_teams()
        return TeamPlan(
            teams=tuple(
                TeamMembership(number, leader, tuple(members))
                for number, (leader, members) in enumerate(
                    zip(self.leaders, source, strict=True), start=1
                )
            ),
            waiting=tuple(self.waiting if waiting is None else waiting),
            undecided=tuple(self.undecided if undecided is None else undecided),
        )

    def present_count(
        self, members: list[Member] | tuple[Member, ...], slot_start: int
    ) -> int:
        """時間帯に参加している人数を返す。"""

        return sum(covers(member, slot_start) for member in members)


tiers = st.sampled_from(tuple(Tier))


@st.composite
def time_windows(draw: st.DrawFn) -> tuple[int, int]:
    """時間帯の境界にそろえない場合も含む、参加開始と終了の分を返す。"""

    start = draw(
        st.sampled_from(SLOT_STARTS)
        | st.integers(min_value=EVENT.start_minutes, max_value=EVENT.end_minutes - 1)
    )
    end = draw(
        st.sampled_from(
            [slot + SLOT_MINUTES for slot in SLOT_STARTS if slot + SLOT_MINUTES > start]
        )
        | st.integers(min_value=start + 1, max_value=EVENT.end_minutes)
    )
    return start, end


def make_member(
    name: str,
    tier: Tier,
    has_vc: bool,
    window: tuple[int, int] | None = None,
) -> Member:
    """全時間帯または指定時間だけ参加するメンバーを作る。"""

    if window is None:
        return Member(name=name, alliance=ALLIANCE, tier=tier, has_vc=has_vc)
    start, end = window
    return Member(
        name=name,
        alliance=ALLIANCE,
        tier=tier,
        has_vc=has_vc,
        starts_at_21=start == KVK_START_MINUTES,
        start_time_minutes=start,
        end_time_minutes=end,
    )


def undecided_member(name: str, tier: Tier, has_vc: bool) -> Member:
    """開始時刻が未定のメンバーを作る。"""

    return Member(
        name=name, alliance=ALLIANCE, tier=tier, has_vc=has_vc, starts_at_21=False
    )


class PowerTie(Enum):
    """上位隊の戦力を意図的に同値にする組み合わせ。"""

    FIRST_EQUALS_SECOND = "1=2"
    """`第1隊 > 第2隊`を破る。ほかの必須条件は満たす。"""
    SECOND_EQUALS_THIRD = "2=3"
    """`第2隊 >= 第3隊`の境界で、必須条件を満たす。"""


@st.composite
def scenarios(draw: st.DrawFn, power_tie: PowerTie | None = None) -> Scenario:
    """全時間帯で必須条件を満たす参加者、指定、所属を生成する。

    `power_tie`を指定すると、上位隊の戦力だけを指定の同値にする。
    """

    # 上位隊は全時間帯に参加するVC可能な8人ずつとし、戦力の高い順に配る。
    top_tiers = sorted(
        draw(
            st.lists(
                tiers,
                min_size=TOP_TEAM_SIZE * TOP_TEAM_COUNT,
                max_size=TOP_TEAM_SIZE * TOP_TEAM_COUNT,
            )
        ),
        key=lambda tier: RULES.tier_power[tier],
        reverse=True,
    )
    chunks = [
        top_tiers[index * TOP_TEAM_SIZE : (index + 1) * TOP_TEAM_SIZE]
        for index in range(TOP_TEAM_COUNT)
    ]
    if power_tie is PowerTie.FIRST_EQUALS_SECOND:
        chunks[1] = chunks[0]
    elif power_tie is PowerTie.SECOND_EQUALS_THIRD:
        chunks[2] = chunks[1]
    teams: list[tuple[Member, ...]] = []
    leaders: list[Member] = []
    for number, chunk in enumerate(chunks, start=1):
        members = tuple(
            make_member(
                f"第{number}隊リーダー" if index == 0 else f"第{number}隊参加者{index}",
                tier,
                has_vc=True,
            )
            for index, tier in enumerate(chunk)
        )
        teams.append(members)
        leaders.append(members[0])
    if power_tie is not PowerTie.FIRST_EQUALS_SECOND:
        assume(team_power(teams[0]) > team_power(teams[1]))

    # 第4隊以降は、途中参加、途中離脱、VC不可、参加時間未定のリーダーを含める。
    undecided: list[Member] = []
    flexible_count = draw(st.integers(min_value=0, max_value=MAXIMUM_FLEXIBLE_TEAMS))
    for number in range(TOP_TEAM_COUNT + 1, TOP_TEAM_COUNT + 1 + flexible_count):
        leader_name = f"第{number}隊リーダー"
        if draw(st.booleans()) and draw(st.booleans()):
            leader = undecided_member(leader_name, draw(tiers), draw(st.booleans()))
            undecided.append(leader)
            members: list[Member] = []
        else:
            leader = make_member(
                leader_name,
                draw(tiers),
                draw(st.booleans()),
                draw(st.none() | time_windows()),
            )
            members = [leader]
        leaders.append(leader)
        other_count = draw(
            st.integers(min_value=0, max_value=MEMBER_CAP - len(members))
        )
        members.extend(
            make_member(
                f"第{number}隊参加者{index}",
                draw(tiers),
                draw(st.booleans()),
                draw(st.none() | time_windows()),
            )
            for index in range(1, other_count + 1)
        )
        # 延長境界時刻より前の休止は必須条件の違反のため、有効な編成には含めない。
        assume(
            all(
                any(covers(member, start) for member in members)
                for start in SLOT_STARTS
                if start < EXTENSION_BOUNDARY_MINUTES
            )
        )
        teams.append(tuple(members))

    waiting = tuple(
        make_member(f"待機参加者{index}", draw(tiers), draw(st.booleans()))
        for index in range(draw(st.integers(min_value=0, max_value=2)))
    )
    undecided.extend(
        undecided_member(f"未定参加者{index}", draw(tiers), draw(st.booleans()))
        for index in range(draw(st.integers(min_value=0, max_value=2)))
    )
    return Scenario(
        teams=tuple(teams),
        leaders=tuple(leaders),
        waiting=waiting,
        undecided=tuple(undecided),
    )


def with_vc(member: Member, has_vc: bool) -> Member:
    """VCだけを変えたメンバーを返す。"""

    return replace(member, has_vc=has_vc)
