"""所属固定のCP-SAT Optimizerのテスト。"""

from dataclasses import replace

import pytest

from deterministic_solver import deterministic_rules
from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.team_building.adapters.optimization.cp_sat_team_optimizer import (
    MembershipOptimizer,
)
from kvk_team.team_building.adapters.optimization.errors import (
    OptimizationError,
    OptimizationTimeoutError,
)
from kvk_team.team_building.application.ports import ProvenInfeasible, SolvedPlan
from kvk_team.team_building.domain.availability import AvailabilityResolver
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.plan import sorties
from kvk_team.team_building.domain.specification import (
    MemberRef,
    OperatorSpecification,
    SpecificationError,
)
from kvk_team.team_building.domain.team import TOP_TEAM_COUNT, TOP_TEAM_SIZE
from kvk_team.team_building.domain.validation import (
    TeamPlanValidator,
    ValidationCode,
)

ALLIANCE = "検証同盟"
TEAM_COUNT = 11
TIERS = (Tier.G8, Tier.G7, Tier.G6, Tier.G5)


def leader(number: int, **changes: object) -> Member:
    """番号の隊のリーダーを作る。上位隊のリーダーはG8とする。"""

    member = Member(
        name=f"リーダー{number:02d}",
        alliance=ALLIANCE,
        tier=Tier.G8 if number <= TOP_TEAM_COUNT else Tier.G5,
        has_vc=True,
    )
    return replace(member, **changes)


def roster(member_count: int = 88, **leader_changes: dict[str, object]) -> list[Member]:
    """11人のリーダーと、全時間帯に参加するVC可能なメンバーの一覧を作る。"""

    leaders = [
        leader(number, **leader_changes.get(f"leader{number}", {}))
        for number in range(1, TEAM_COUNT + 1)
    ]
    others = [
        Member(
            name=f"参加者{index:03d}",
            alliance=ALLIANCE,
            tier=TIERS[index % len(TIERS)],
            has_vc=True,
        )
        for index in range(member_count - len(leaders))
    ]
    return [*leaders, *others]


def specification(team_count: int = TEAM_COUNT) -> OperatorSpecification:
    """リーダー一覧の運用者の指定を作る。"""

    return OperatorSpecification(
        leaders=tuple(
            MemberRef(f"リーダー{number:02d}", ALLIANCE)
            for number in range(1, team_count + 1)
        )
    )


def solve(
    members: list[Member], spec: OperatorSpecification | None = None
) -> SolvedPlan:
    """既定の決定的な設定で解き、解ありであることを確かめて返す。"""

    outcome = MembershipOptimizer(deterministic_rules()).optimize(
        members, spec or specification()
    )
    assert isinstance(outcome, SolvedPlan), outcome
    return outcome


@pytest.fixture(scope="module")
def solved() -> SolvedPlan:
    """時間のかかる共通の編成を1回だけ生成する。"""

    return solve(roster())


def test_optimizer_builds_one_team_per_leader_with_fixed_membership(
    solved: SolvedPlan,
) -> None:
    """リーダーの人数の隊を作り、リーダーを自分の隊に置き、独立Validatorが受理する（FRM-001、FRM-002）。"""

    members = roster()
    plan = solved.plan
    report = TeamPlanValidator(deterministic_rules()).validate(
        plan, members, specification()
    )

    assert report.issues == ()
    assert [team.number for team in plan.teams] == list(range(1, TEAM_COUNT + 1))
    for team in plan.teams:
        assert team.leader == leader(team.number)
        assert team.members[0] == team.leader
    for team in plan.teams[:TOP_TEAM_COUNT]:
        assert len(team.members) == TOP_TEAM_SIZE
        assert all(member.has_vc for member in team.members)
    for team in plan.teams[TOP_TEAM_COUNT:]:
        assert len(team.members) <= deterministic_rules().member_cap
    # 88人は上限の合計96人に収まるため待機は出ない。出撃の指標は隊と時間帯ごとに1件ある。
    assert plan.waiting == ()
    assert len(report.sortie_metrics) == TEAM_COUNT * len(
        deterministic_rules().time_slots
    )


def test_optimizer_places_overflow_members_in_waiting() -> None:
    """上限を超える参加者は、解なしにせず待機として残す（FRM-010、FRM-033）。"""

    rules = deterministic_rules()
    capacity = (
        TOP_TEAM_COUNT * TOP_TEAM_SIZE
        + (TEAM_COUNT - TOP_TEAM_COUNT) * rules.member_cap
    )
    members = roster(capacity + 3)

    solved = solve(members)
    report = TeamPlanValidator(rules).validate(solved.plan, members, specification())

    assert report.issues == ()
    assert len(solved.plan.waiting) == 3


def test_optimizer_separates_undecided_members_and_leader() -> None:
    """開始時刻が未定のメンバーとリーダーを別枠へ置き、リーダー不在の隊も作る（FRM-002、FRM-060）。"""

    undecided_member = Member(
        name="未定参加者",
        alliance=ALLIANCE,
        tier=Tier.G6,
        has_vc=True,
        starts_at_21=False,
    )
    members = [*roster(leader5={"starts_at_21": False}), undecided_member]

    solved = solve(members)
    team5 = solved.plan.team(5)
    report = TeamPlanValidator(deterministic_rules()).validate(
        solved.plan, members, specification()
    )

    assert set(solved.plan.undecided) == {undecided_member, team5.leader}
    assert not team5.leader_is_member
    assert team5.members
    assert report.issues == ()
    assert any(
        warning.code is ValidationCode.LEADER_ABSENT and warning.team_number == 5
        for warning in report.warnings
    )


def test_optimizer_allows_seven_in_top_team_while_leader_is_absent() -> None:
    """上位隊のリーダーが遅れる時間帯は7人で出撃させ、警告を出す（FRM-020、FRM-029）。"""

    rules = deterministic_rules()
    members = roster(leader1={"starts_at_21": False, "start_time_minutes": 22 * 60})

    solved = solve(members)
    partition = AvailabilityResolver(rules.team_master.event_time).partition(members)
    first_team = [
        sortie
        for sortie in sorties(solved.plan, partition.confirmed, rules.time_slots)
        if sortie.team_number == 1
    ]
    report = TeamPlanValidator(rules).validate(solved.plan, members, specification())

    assert report.issues == ()
    assert [len(sortie.members) for sortie in first_team[:2]] == [7, 7]
    assert all(len(sortie.members) == 8 for sortie in first_team[2:])
    assert {
        warning.time_slot.start_minutes
        for warning in report.warnings
        if warning.code is ValidationCode.LEADER_ABSENT
        and warning.team_number == 1
        and warning.time_slot is not None
    } == {21 * 60, 21 * 60 + 30}


def test_optimizer_returns_rest_when_no_member_can_join_before_boundary() -> None:
    """延長境界時刻より前の休止が避けられない編成を、最適だと示して返す（FRM-048）。

    第4隊のリーダーだけが22:00から参加し、ほかのメンバーは上位隊で尽きる。
    """

    top_others = TOP_TEAM_COUNT * (TOP_TEAM_SIZE - 1)
    members = [
        *(leader(number) for number in range(1, TOP_TEAM_COUNT + 1)),
        leader(4, starts_at_21=False, start_time_minutes=22 * 60),
        *roster(TEAM_COUNT + top_others)[TEAM_COUNT:],
    ]
    assert len(members) == TOP_TEAM_COUNT * TOP_TEAM_SIZE + 1
    spec = specification(4)

    solved = solve(members, spec)
    report = TeamPlanValidator(deterministic_rules()).validate(
        solved.plan, members, spec
    )

    assert solved.proven_optimal
    assert report.has_only_shortfalls
    assert {
        (issue.team_number, issue.time_slot.start_minutes)
        for issue in report.shortfalls
        if issue.time_slot is not None
    } == {(4, 21 * 60), (4, 21 * 60 + 30)}


def test_optimizer_reports_vc_shortage_with_reason() -> None:
    """上位隊に必要な常時参加のVC可能なメンバーが足りない場合は、理由を示して解なしとする。"""

    members = [
        replace(member, has_vc=False) if member.name.startswith("参加者") else member
        for member in roster()
    ]

    outcome = MembershipOptimizer(deterministic_rules()).optimize(
        members, specification()
    )

    assert isinstance(outcome, ProvenInfeasible)
    assert "全時間帯に参加しVC可能なメンバーが不足しています" in outcome.reason
    # 第4隊以降のリーダー（VC可能）は上位隊に入れないため数えない
    assert "0人（必要: 21人）" in outcome.reason


def test_optimizer_reports_top_leader_without_vc() -> None:
    """VC不可の上位隊のリーダーは、理由を示して解なしとする（FRM-021）。"""

    outcome = MembershipOptimizer(deterministic_rules()).optimize(
        roster(leader2={"has_vc": False}), specification()
    )

    assert isinstance(outcome, ProvenInfeasible)
    assert "第2隊のリーダー" in outcome.reason


def test_optimizer_reports_proven_infeasible_power_order() -> None:
    """全員が同じTierで第1隊 > 第2隊を満たせない場合は、解がないと証明した結果を返す。"""

    members = [replace(member, tier=Tier.G5) for member in roster()]

    outcome = MembershipOptimizer(deterministic_rules()).optimize(
        members, specification()
    )

    assert isinstance(outcome, ProvenInfeasible)
    assert "存在しません" in outcome.reason


def test_optimizer_rejects_leader_missing_from_roster() -> None:
    """リーダー一覧のメンバーが参加者一覧にいなければ入力のエラーにする（FRM-047）。"""

    members = [member for member in roster() if member.name != "リーダー07"]

    with pytest.raises(SpecificationError, match="7番目.*見つかりません"):
        MembershipOptimizer(deterministic_rules()).optimize(members, specification())


def test_optimizer_returns_identical_plan_for_same_input(solved: SolvedPlan) -> None:
    """決定的時間で打ち切る単一workerの探索は、同じ入力へ同じ編成を返す。"""

    assert solve(roster()) == solved


def test_optimizer_reports_timeout_separately_from_infeasibility() -> None:
    """解が見つかる前に探索上限へ達した場合は、時間切れとして報告する（ADR 0019）。"""

    rules = deterministic_rules(deterministic_time=0.0001)

    with pytest.raises(OptimizationTimeoutError, match="時間切れ") as raised:
        MembershipOptimizer(rules).optimize(roster(), specification())

    assert isinstance(raised.value, OptimizationError)
    assert "編成が存在しないとは確定していません" in str(raised.value)


@pytest.mark.parametrize("deterministic_time", [0.0, -1.0])
def test_rules_reject_non_positive_deterministic_time(
    deterministic_time: float,
) -> None:
    """決定的時間の上限は正の値だけを受け付ける。"""

    with pytest.raises(ValueError, match="deterministic time"):
        replace(default_rules(), maximum_deterministic_time=deterministic_time)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("maximum_optimization_seconds", 0.0, "optimization time limit"),
        ("maximum_optimization_seconds", -1.0, "optimization time limit"),
        ("solver_worker_count", 0, "solver worker count"),
        ("maximum_validation_attempts", 0, "validation attempt count"),
    ],
)
def test_rules_reject_invalid_limits_when_overridden(
    field_name: str,
    value: float,
    message: str,
) -> None:
    """既定ルールを上書きしても、有効な編成を表現できない値は拒否する。"""

    with pytest.raises(ValueError, match=message):
        replace(default_rules(), **{field_name: value})


def _full_time(name: str, tier: Tier, has_vc: bool = True) -> Member:
    return Member(name=name, alliance=ALLIANCE, tier=tier, has_vc=has_vc)


def _leaving(name: str, tier: Tier) -> Member:
    """23:00に抜けるVC可能なメンバーを作る。"""

    return Member(name, ALLIANCE, tier, has_vc=True, end_time_minutes=23 * 60)


def test_optimizer_does_not_swap_top_team_members_mid_battle() -> None:
    """途中で抜ける人と途中から来る人を組めば上位隊の戦力関係を満たせる場合も、入れ替えない。

    全時間帯に参加するG5だけでは3隊の戦力が並ぶため、解がないことを証明して返す（FRM-020〜FRM-022）。
    """

    joining = Member(
        "途中から来る人",
        ALLIANCE,
        Tier.G8,
        has_vc=True,
        starts_at_21=False,
        start_time_minutes=23 * 60,
    )
    members = [
        *(leader(number) for number in range(1, TOP_TEAM_COUNT + 1)),
        *(_full_time(f"G5参加者{index}", Tier.G5) for index in range(21)),
        _leaving("途中で抜ける人", Tier.G8),
        joining,
    ]

    outcome = MembershipOptimizer(deterministic_rules()).optimize(
        members, specification(TOP_TEAM_COUNT)
    )

    assert isinstance(outcome, ProvenInfeasible)
    assert "存在しません" in outcome.reason


def test_optimizer_keeps_partial_members_out_of_top_teams() -> None:
    """途中で抜けるG8と途中から来るG8がいても、上位隊のリーダー以外は全時間帯に参加する人だけにする。

    全時間帯に参加するG8（リーダー以外）を18人にする。入れ替わりなしでは第1隊3200、第2隊3100、
    第3隊3000が上位隊の戦力の最大で、抜ける人と来る人の2人で第3隊の1枠を埋めれば第3隊は3100に上がる。
    第4隊以降は全時間帯で8人以上を保てるため、常時稼働の制約がなければ、最下段の上位隊の戦力のために
    入れ替わりを選ぶ（解がある入力）。
    """

    base = roster()
    g8_others = [
        index
        for index, member in enumerate(base)
        if member.tier is Tier.G8 and member.name.startswith("参加者")
    ]
    assert len(g8_others) == 20
    for index in g8_others[:2]:
        base[index] = replace(base[index], tier=Tier.G7)
    joining = [
        Member(
            f"途中から来るG8{index}",
            ALLIANCE,
            Tier.G8,
            has_vc=True,
            starts_at_21=False,
            start_time_minutes=23 * 60,
        )
        for index in range(4)
    ]
    partial = [
        *(_leaving(f"途中で抜けるG8{index}", Tier.G8) for index in range(4)),
        *joining,
    ]
    members = [*base, *partial]

    solved = solve(members)
    report = TeamPlanValidator(deterministic_rules()).validate(
        solved.plan, members, specification()
    )

    assert solved.proven_optimal
    assert report.issues == ()
    for team in solved.plan.teams[:TOP_TEAM_COUNT]:
        assert not set(team.members) & set(partial)
    assert {
        metric.power for metric in report.sortie_metrics if metric.team_number == 3
    } == {3000}


def test_optimizer_reports_shortage_when_vc_members_leave_mid_battle() -> None:
    """途中で抜けるVC可能な人は上位隊に数えず、全時間帯に参加する人の不足を理由に示す。"""

    members = [
        *(leader(number) for number in range(1, TOP_TEAM_COUNT + 1)),
        *(_full_time(f"常時参加{index}", Tier.G6) for index in range(20)),
        *(_leaving(f"途中で抜ける人{index}", Tier.G6) for index in range(5)),
    ]

    outcome = MembershipOptimizer(deterministic_rules()).optimize(
        members, specification(TOP_TEAM_COUNT)
    )

    assert isinstance(outcome, ProvenInfeasible)
    assert "20人（必要: 21人）" in outcome.reason


def test_optimizer_keeps_top_team_at_seven_when_leader_is_undecided() -> None:
    """上位隊のリーダーが参加時間未定なら別枠に置き、その隊は全時間帯を7人で警告にする（FRM-021）。"""

    rules = deterministic_rules()
    members = roster(leader2={"starts_at_21": False})

    solved = solve(members)
    team2 = solved.plan.team(2)
    report = TeamPlanValidator(rules).validate(solved.plan, members, specification())

    assert report.issues == ()
    assert team2.leader in solved.plan.undecided
    assert len(team2.members) == TOP_TEAM_SIZE - 1
    assert {
        metric.member_count
        for metric in report.sortie_metrics
        if metric.team_number == 2
    } == {TOP_TEAM_SIZE - 1}
    absent = {
        warning.time_slot.start_minutes
        for warning in report.warnings
        if warning.code is ValidationCode.LEADER_ABSENT
        and warning.team_number == 2
        and warning.time_slot is not None
    }
    assert absent == {slot.start_minutes for slot in rules.time_slots}


def test_optimizer_spreads_shortage_between_teams() -> None:
    """8人に足りない人数を隊の間で均す（ADR 0034の暫定の目的関数。2乗の和）。

    第4隊と第5隊へ回せるのはリーダーのほかに8人で、2乗の和では5人と5人が最もよい。
    FRM-031の「8人未満の（隊、時間帯）の数」をそのまま使うと、片方の隊を8人にそろえる配り方
    （2人と8人）が最もよくなるため、このテストが失敗する（確かめ済み）。足りない人数の合計（線形）は配り方に
    よらず同じ値で、どの配り方も最適になるため、線形への後退はこのテストでは区別できない。
    """

    members = [
        *(leader(number) for number in range(1, 6)),
        *(
            _full_time(f"上位隊候補{index}", TIERS[index % len(TIERS)])
            for index in range(TOP_TEAM_COUNT * (TOP_TEAM_SIZE - 1))
        ),
        *(
            _full_time(f"第4隊以降の候補{index}", Tier.G5, has_vc=False)
            for index in range(8)
        ),
    ]

    solved = solve(members, specification(5))

    assert solved.proven_optimal
    assert [len(solved.plan.team(number).members) for number in (4, 5)] == [5, 5]
    assert solved.plan.waiting == ()
