"""遅れて出撃する隊と応援をOptimizerが守るかのテスト（FRM-041、FRM-042、FRM-047、FRM-048）。

決定的な探索設定で、運用者の指定どおりの出撃開始時刻と応援先を持ち、独立Validatorが受理する
編成を返すことを確かめる。名前は架空である。
"""

from deterministic_solver import deterministic_rules
from kvk_team.team_building.adapters.optimization.cp_sat_team_optimizer import (
    MembershipOptimizer,
)
from kvk_team.team_building.application.ports import ProvenInfeasible, SolvedPlan
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.plan import Support, TimeSlot
from kvk_team.team_building.domain.specification import (
    LateStart,
    MemberRef,
    OperatorSpecification,
    SupportRef,
)
from kvk_team.team_building.domain.validation import (
    TeamPlanValidator,
    ValidationCode,
)

RULES = deterministic_rules()
EVENT = RULES.team_master.event_time
ALLIANCE = "検証同盟"
H21 = EVENT.start_minutes
H2130 = H21 + 30
H22 = H21 + 60
SLOT21 = TimeSlot(H21, H2130)
SLOT2130 = TimeSlot(H2130, H22)
TOP_TIERS = (Tier.G8, Tier.G7, Tier.G6)


def _member(
    name: str,
    tier: Tier = Tier.G5,
    has_vc: bool = True,
    start: int | None = None,
    end: int | None = None,
) -> Member:
    return Member(
        name=name,
        alliance=ALLIANCE,
        tier=tier,
        has_vc=has_vc,
        start_time_minutes=EVENT.start_minutes if start is None else start,
        end_time_minutes=EVENT.end_minutes if end is None else end,
    )


LEADERS = (
    *(_member(f"リーダー{number}", Tier.G8) for number in (1, 2, 3)),
    _member("リーダー4"),
    _member("リーダー5"),
    _member("リーダー6", start=H22),
)
TOP_MEMBERS = tuple(
    _member(f"上位{index:02d}", TOP_TIERS[index % len(TOP_TIERS)])
    for index in range(21)
)
LATER = tuple(_member(f"後半{index}", start=H22) for index in range(6))
EARLY = (_member("早い人1", end=H22), _member("早い人2", end=H22))
OTHER_EARLY = _member("早い人3", end=H22)


def _specification(*late_starts: LateStart) -> OperatorSpecification:
    return OperatorSpecification(
        leaders=tuple(MemberRef(leader.name, ALLIANCE) for leader in LEADERS),
        late_starts=late_starts,
    )


def _supports(target: int = 5) -> tuple[SupportRef, ...]:
    return tuple(
        SupportRef(MemberRef(member.name, ALLIANCE), slot.start_minutes, target)
        for member in EARLY
        for slot in (SLOT21, SLOT2130)
    )


def _solve(members: list[Member], specification: OperatorSpecification) -> SolvedPlan:
    outcome = MembershipOptimizer(RULES).optimize(members, specification)
    assert isinstance(outcome, SolvedPlan), outcome
    report = TeamPlanValidator(RULES).validate(outcome.plan, members, specification)
    assert report.issues == (), report.issues
    return outcome


def test_team_without_early_members_rests_in_opening_without_answer() -> None:
    """序盤に参加する所属メンバーがいない隊は、遅れて出撃させなければ休止になる（前提の確認）。"""

    members = [*LEADERS, *TOP_MEMBERS, *LATER]
    outcome = MembershipOptimizer(RULES).optimize(members, _specification())
    assert isinstance(outcome, SolvedPlan)

    report = TeamPlanValidator(RULES).validate(outcome.plan, members, _specification())

    assert {
        (issue.code, issue.team_number, issue.time_slot) for issue in report.issues
    } == {(ValidationCode.REST, 6, SLOT21), (ValidationCode.REST, 6, SLOT2130)}


def test_allowed_shortfalls_limit_rest_before_boundary() -> None:
    """休止を許す（隊、時間帯）を渡すと、それ以外の休止をなくす編成だけを探す（作成者の仮定A-41）。"""

    members = [*LEADERS, *TOP_MEMBERS, *LATER]
    optimizer = MembershipOptimizer(RULES)
    allowed = frozenset({(6, H21), (6, H2130)})

    blocked = optimizer.optimize(members, _specification(), frozenset({(6, H21)}))
    permitted = optimizer.optimize(members, _specification(), allowed)
    late = optimizer.optimize(members, _specification(LateStart(6, H22)), frozenset())

    assert isinstance(blocked, ProvenInfeasible)
    assert "休止を許した隊と時間帯の外に休止がない" in blocked.reason
    assert isinstance(permitted, SolvedPlan)
    assert isinstance(late, SolvedPlan)


def test_late_team_does_not_rest_before_its_start() -> None:
    """遅れて出撃する隊は、出撃開始前の時間帯を休止にしない（FRM-041、FRM-048）。"""

    members = [*LEADERS, *TOP_MEMBERS, *LATER]
    specification = _specification(LateStart(6, H22))

    solved = _solve(members, specification)

    assert solved.plan.team(6).start_minutes == H22
    assert solved.plan.supports == ()


def test_supporters_stay_in_late_team_and_count_for_target() -> None:
    """応援するメンバーは遅れて出撃する隊に所属し、応援先の出撃人数に数える（作成者の仮定A-16）。"""

    members = [*LEADERS, *TOP_MEMBERS, *LATER, *EARLY]
    specification = _specification(LateStart(6, H22, _supports()))

    solved = _solve(members, specification)

    plan = solved.plan
    assert set(EARLY) <= set(plan.team(6).members)
    assert set(plan.supports) == {
        Support(member, slot, 5) for member in EARLY for slot in (SLOT21, SLOT2130)
    }
    report = TeamPlanValidator(RULES).validate(plan, members, specification)
    metric = {
        (item.team_number, item.time_slot): item for item in report.sortie_metrics
    }
    assert metric[5, SLOT21].support_count == 2


def _crowded_opening() -> tuple[list[Member], tuple[Member, ...]]:
    """21:00に第4隊と第5隊を上限まで埋められる常時参加者と、応援先のない序盤の参加者を作る。

    第5隊は応援2人を受けるため、所属メンバーは21:00に上限より2人少なくまでしか参加できない。
    常時参加者は出撃開始前に参加するため、第6隊に入れない。このため、応援を上限に数えない誤りと、
    応援先のない序盤の参加者を第6隊に入れる誤りは、どちらも待機を減らす（目的の5段目）ことになり、
    制約がなければ目的関数がその誤りを選ぶ。
    """

    capacity = (RULES.member_cap - 1) + (RULES.member_cap - 1 - len(EARLY))
    fillers = tuple(
        _member(f"常時{index:02d}", has_vc=False) for index in range(capacity + 1)
    )
    members = [*LEADERS, *TOP_MEMBERS, *LATER, *EARLY, OTHER_EARLY, *fillers]
    return members, fillers


def test_pre_start_member_without_support_is_not_placed_in_late_team() -> None:
    """応援先のない出撃開始前の参加者は、待機を増やしても遅れて出撃する隊に入れない（FRM-047）。"""

    members, _ = _crowded_opening()
    specification = _specification(LateStart(6, H22, _supports()))

    solved = _solve(members, specification)

    assert OTHER_EARLY in solved.plan.waiting
    assert OTHER_EARLY not in solved.plan.team(6).members


def test_supported_target_counts_supporters_for_cap() -> None:
    """応援を数えて上限を超えないよう、応援先の所属メンバーを減らす（FRM-030、FRM-042）。"""

    members, fillers = _crowded_opening()
    specification = _specification(LateStart(6, H22, _supports()))

    solved = _solve(members, specification)

    own_fifth = [
        member for member in solved.plan.team(5).members if member != LEADERS[4]
    ]
    assert len(own_fifth) == RULES.member_cap - 1 - len(EARLY)
    assert len(set(solved.plan.waiting) & set(fillers)) == 1


def test_supported_target_keeps_own_member_present() -> None:
    """応援を受ける時間帯の応援先には、所属メンバーを1人以上参加させる（FRM-042、FRM-048）。

    第4隊と第5隊のリーダーは22:00から来る。21:00の常時参加者は1人で、どちらに入れても休止の数は同じ。
    人数の段では第4隊に入れるほうがよいため、制約がなければ第5隊が休止したまま応援を受ける。
    """

    late_leaders = (
        *LEADERS[:3],
        _member("リーダー4", start=H22),
        _member("リーダー5", start=H22),
        LEADERS[5],
    )
    only = _member("常時だけ", has_vc=False)
    members = [*late_leaders, *TOP_MEMBERS, *LATER, *EARLY, only]
    specification = OperatorSpecification(
        leaders=tuple(MemberRef(leader.name, ALLIANCE) for leader in late_leaders),
        late_starts=(LateStart(6, H22, _supports()),),
    )

    outcome = MembershipOptimizer(RULES).optimize(members, specification)

    assert isinstance(outcome, SolvedPlan), outcome
    assert only in outcome.plan.team(5).members
    report = TeamPlanValidator(RULES).validate(outcome.plan, members, specification)
    assert {
        (issue.code, issue.team_number, issue.time_slot) for issue in report.issues
    } == {(ValidationCode.REST, 4, SLOT21), (ValidationCode.REST, 4, SLOT2130)}


def test_support_to_team_before_its_start_is_proven_infeasible() -> None:
    """出撃開始前の隊を応援先にする指定は、成り立たないと理由を示して返す（FRM-042）。"""

    members = [*LEADERS, *TOP_MEMBERS, *LATER, *EARLY]
    specification = _specification(
        LateStart(5, H22), LateStart(6, H22, _supports(target=5))
    )

    outcome = MembershipOptimizer(RULES).optimize(members, specification)

    assert isinstance(outcome, ProvenInfeasible)
    assert "第6隊の21:00の第5隊への応援" in outcome.reason
    assert "出撃開始前" in outcome.reason
    assert "番目" not in outcome.reason
