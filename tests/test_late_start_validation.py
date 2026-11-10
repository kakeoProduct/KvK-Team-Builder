"""遅れて出撃する隊と応援の独立検証のテスト（FRM-041、FRM-042、FRM-047、FRM-048）。

Optimizerを信用せず、決め打ちの編成を直接Validatorへ与えて受理と拒否を確かめる。
名前は架空である。
"""

from dataclasses import dataclass, replace

import pytest

from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.plan import (
    Support,
    TeamMembership,
    TeamPlan,
    TimeSlot,
)
from kvk_team.team_building.domain.specification import (
    LateStart,
    MemberRef,
    OperatorSpecification,
    SupportRef,
)
from kvk_team.team_building.domain.validation import (
    TeamPlanValidator,
    ValidationCode,
    ValidationReport,
)

RULES = default_rules()
EVENT = RULES.team_master.event_time
ALLIANCE = "検証同盟"
H21 = EVENT.start_minutes
H2130 = H21 + 30
H22 = H21 + 60
SLOT21 = TimeSlot(H21, H2130)
SLOT2130 = TimeSlot(H2130, H22)


def _member(
    name: str,
    tier: Tier = Tier.G6,
    start: int | None = None,
    end: int | None = None,
) -> Member:
    return Member(
        name=name,
        alliance=ALLIANCE,
        tier=tier,
        has_vc=True,
        start_time_minutes=EVENT.start_minutes if start is None else start,
        end_time_minutes=EVENT.end_minutes if end is None else end,
    )


@dataclass(frozen=True)
class Scenario:
    """第1〜3隊（8人）、第4隊、第5隊（応援先）、遅れて出撃する第6隊の編成。"""

    teams: tuple[tuple[Member, ...], ...]
    early: tuple[Member, ...]
    starts: tuple[int | None, ...]
    supports: tuple[Support, ...]
    late_starts: tuple[LateStart, ...]
    extra: tuple[Member, ...] = ()

    @property
    def members(self) -> list[Member]:
        return [member for team in self.teams for member in team] + list(self.extra)

    @property
    def specification(self) -> OperatorSpecification:
        return OperatorSpecification(
            leaders=tuple(MemberRef(team[0].name, ALLIANCE) for team in self.teams),
            late_starts=self.late_starts,
        )

    def plan(self) -> TeamPlan:
        return TeamPlan(
            teams=tuple(
                TeamMembership(number, team[0], team, start)
                for number, (team, start) in enumerate(
                    zip(self.teams, self.starts, strict=True), start=1
                )
            ),
            waiting=self.extra,
            undecided=(),
            supports=self.supports,
        )

    def validate(self) -> ValidationReport:
        return TeamPlanValidator(RULES).validate(
            self.plan(), self.members, self.specification
        )


def _top_team(number: int, tier: Tier) -> tuple[Member, ...]:
    return tuple(_member(f"第{number}隊の{index}", tier) for index in range(8))


def _scenario(fifth_size: int = 4, fifth_start: int | None = None) -> Scenario:
    """第6隊は22:00から出撃し、21:00から22:00まで参加する2人が第5隊を応援する。"""

    tops = (_top_team(1, Tier.G8), _top_team(2, Tier.G7), _top_team(3, Tier.G7))
    fourth = (_member("第4隊の0", Tier.G5),)
    fifth = tuple(
        _member(f"第5隊の{index}", Tier.G5, start=fifth_start)
        for index in range(fifth_size)
    )
    early = (
        _member("早い人1", Tier.G5, end=H22),
        _member("早い人2", Tier.G5, end=H22),
    )
    sixth = (
        _member("第6隊の0", Tier.G5, start=H22),
        *early,
        _member("遅い人", start=H22),
    )
    supports = tuple(
        Support(member, slot, 5) for member in early for slot in (SLOT21, SLOT2130)
    )
    late = LateStart(
        6,
        H22,
        tuple(
            SupportRef(MemberRef(member.name, ALLIANCE), slot.start_minutes, 5)
            for member in early
            for slot in (SLOT21, SLOT2130)
        ),
    )
    return Scenario(
        teams=(*tops, fourth, fifth, sixth),
        early=early,
        starts=(None, None, None, None, None, H22),
        supports=supports,
        late_starts=(late,),
    )


def _codes(report: ValidationReport) -> set[ValidationCode]:
    return {issue.code for issue in report.issues}


def test_validator_accepts_late_team_and_counts_supporters_for_target() -> None:
    """出撃開始前は休止にせず、応援を応援先の出撃人数に数える（FRM-011、FRM-041、FRM-042）。"""

    report = _scenario().validate()

    assert report.issues == ()
    metric = {
        (item.team_number, item.time_slot): item for item in report.sortie_metrics
    }
    assert metric[5, SLOT21].member_count == 6
    assert metric[5, SLOT21].support_count == 2
    assert not metric[6, SLOT21].started
    assert metric[6, SLOT21].member_count == 0
    assert metric[6, TimeSlot(H22, H22 + 30)].started
    assert not any(
        warning.team_number == 6 and warning.time_slot in (SLOT21, SLOT2130)
        for warning in report.warnings
    )


def test_validator_rejects_start_time_different_from_specification() -> None:
    """編成の出撃開始時刻が運用者の指定と違えば拒否する（FRM-047）。"""

    scenario = _scenario()
    changed = replace(scenario, starts=(None, None, None, None, None, H22 + 30))

    assert ValidationCode.SPECIFICATION_MISMATCH in _codes(changed.validate())


def test_validator_rejects_late_start_without_specification() -> None:
    """運用者の指定にない遅れて出撃する隊を拒否する（FIXの隊の例外は分割案の5）。"""

    scenario = _scenario()
    changed = replace(scenario, late_starts=())

    assert ValidationCode.SPECIFICATION_MISMATCH in _codes(changed.validate())


def test_validator_rejects_top_team_starting_late() -> None:
    """第1〜3隊は遅れて出撃させられない（FRM-041）。"""

    scenario = _scenario()
    changed = replace(scenario, starts=(None, H22, None, None, None, H22))

    assert ValidationCode.LATE_START in _codes(changed.validate())


def test_validator_rejects_supports_different_from_specification() -> None:
    """編成の応援先が運用者の指定と違えば拒否する（FRM-047）。"""

    scenario = _scenario()
    moved = tuple(
        replace(support, team_number=4) if support.time_slot == SLOT21 else support
        for support in scenario.supports
    )
    changed = replace(scenario, supports=moved)

    assert ValidationCode.SPECIFICATION_MISMATCH in _codes(changed.validate())


NOT_PRE_START_MEMBER = "遅れて出撃する隊の出撃開始前の所属メンバーによるもの"
OTHER_TEAM = "第5隊以降の、ほかの隊"
OFF_GRID = "時間帯の区切りにありません"


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("team4", OTHER_TEAM),
        ("unknown_target", OTHER_TEAM),
        ("own_team", OTHER_TEAM),
        ("after_start", NOT_PRE_START_MEMBER),
        ("not_member", NOT_PRE_START_MEMBER),
        ("absent", "参加していないため応援できません"),
        ("missing", "出撃開始前に参加しているため、応援先が要ります"),
        ("duplicate", "同じ時間帯の応援先が2つ以上"),
        ("off_grid", OFF_GRID),
        ("after_end", OFF_GRID),
    ],
)
def test_validator_rejects_invalid_support_even_if_specification_agrees(
    case: str, message: str
) -> None:
    """FRM-042の条件を満たさない応援を、運用者の指定との一致とは別に拒否する。

    戦闘時間の時間帯にない応援も、例外で止まらずに拒否する。
    """

    scenario = _scenario()
    first, second = scenario.early
    supports = list(scenario.supports)
    teams = [list(team) for team in scenario.teams]
    if case == "team4":
        supports[0] = replace(supports[0], team_number=4)
    elif case == "unknown_target":
        supports[0] = replace(supports[0], team_number=99)
    elif case == "own_team":
        supports[0] = replace(supports[0], team_number=6)
    elif case == "off_grid":
        supports.append(Support(first, TimeSlot(H21 + 15, H21 + 45), 5))
    elif case == "after_end":
        end = EVENT.end_minutes
        supports.append(Support(first, TimeSlot(end, end + 30), 5))
    elif case == "after_start":
        supports.append(Support(scenario.teams[5][3], TimeSlot(H22, H22 + 30), 5))
    elif case == "absent":
        supports.append(Support(scenario.teams[5][3], SLOT21, 5))
    elif case == "not_member":
        teams[5].remove(first)
        teams[4].append(first)
    elif case == "missing":
        supports = [support for support in supports if support.member != second]
    elif case == "duplicate":
        supports.append(Support(first, SLOT21, 5))
    plan = replace(
        scenario.plan(),
        supports=tuple(supports),
        teams=tuple(
            replace(membership, members=tuple(team))
            for membership, team in zip(scenario.plan().teams, teams, strict=True)
        ),
    )
    report = TeamPlanValidator(RULES).validate(
        plan, scenario.members, scenario.specification
    )

    assert any(
        issue.code is ValidationCode.SUPPORT and message in issue.message
        for issue in report.issues
    ), report.issues


def test_validator_rejects_support_over_target_cap() -> None:
    """応援を数えて上限を超える応援先を拒否する（FRM-030、FRM-042、作成者の仮定A-04）。"""

    scenario = _scenario(fifth_size=RULES.member_cap)

    report = scenario.validate()

    assert {
        (issue.code, issue.team_number, issue.time_slot) for issue in report.issues
    } == {
        (ValidationCode.CAPACITY, 5, SLOT21),
        (ValidationCode.CAPACITY, 5, SLOT2130),
    }


def test_validator_rejects_support_to_resting_target() -> None:
    """所属メンバーが0人の時間帯の隊は応援先にならない（FRM-048）。"""

    scenario = _scenario(fifth_start=H22)

    report = scenario.validate()

    assert ValidationCode.SUPPORT in _codes(report)


def test_validator_rejects_support_to_team_before_its_start() -> None:
    """出撃開始前の隊は応援先にならない（FRM-042の「出撃中」）。"""

    # 第5隊の所属メンバーは22:00から参加させ、出撃開始前の参加に応援先がない理由では拒否されない
    # ようにする。応援先が出撃開始前であることだけで拒否されることを確かめる。
    scenario = _scenario(fifth_start=H22)
    changed = replace(scenario, starts=(None, None, None, None, H22, H22))

    report = changed.validate()

    support_issues = [
        issue for issue in report.issues if issue.code is ValidationCode.SUPPORT
    ]
    assert support_issues
    assert all(
        "出撃開始前です" in issue.message and issue.team_number == 5
        for issue in support_issues
    ), support_issues


@pytest.mark.parametrize("start", [H22 + 15, H21])
def test_validator_rejects_start_time_off_grid_or_at_battle_start(start: int) -> None:
    """出撃開始時刻は戦闘開始より後の時間帯の区切りにする（FRM-047）。指定と一致していても拒否する。"""

    scenario = _scenario()
    changed = replace(
        scenario,
        starts=(None, None, None, None, None, start),
        supports=(),
        late_starts=(LateStart(6, start),),
    )

    codes = _codes(changed.validate())

    assert ValidationCode.LATE_START in codes
    assert ValidationCode.SPECIFICATION_MISMATCH not in codes


def test_validator_rejects_supporter_in_other_late_team() -> None:
    """応援するメンバーは、指定した遅れて出撃する隊に所属する（FRM-047、作成者の仮定A-16）。

    ほかの遅れて出撃する隊に所属させた編成は、応援の条件を満たしても指定と違うとして拒否する。
    """

    scenario = _scenario()
    seventh = (_member("第7隊の0", Tier.G5, start=H22),)
    first = scenario.early[0]
    sixth = tuple(member for member in scenario.teams[5] if member != first)
    changed = replace(
        scenario,
        teams=(*scenario.teams[:5], sixth, (*seventh, first)),
        starts=(*scenario.starts, H22),
        late_starts=(*scenario.late_starts, LateStart(7, H22)),
    )

    report = changed.validate()

    assert ValidationCode.SPECIFICATION_MISMATCH in _codes(report)
    assert not any(issue.code is ValidationCode.SUPPORT for issue in report.issues), (
        report.issues
    )


def test_validator_rejects_pre_start_member_without_support() -> None:
    """出撃開始前に参加している所属メンバーには、時間帯ごとに応援先が要る（FRM-047）。"""

    scenario = _scenario()
    another = _member("早い人3", Tier.G5, end=H22)
    teams = list(scenario.teams)
    teams[5] = (*teams[5], another)
    changed = replace(scenario, teams=tuple(teams))

    assert ValidationCode.SUPPORT in _codes(changed.validate())
