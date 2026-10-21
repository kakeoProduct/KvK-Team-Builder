"""時間帯別CP-SAT Optimizerのテスト。"""

from dataclasses import replace

import pytest

from deterministic_solver import deterministic_rules
from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.team_building.adapters.optimization.cp_sat_team_optimizer import (
    TimeSlotTeamOptimizer,
)
from kvk_team.team_building.adapters.optimization.errors import (
    InfeasibleRosterError,
    OptimizationError,
    OptimizationTimeoutError,
)
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.team import TeamLabel


def make_dynamic_roster(extra_member_count: int = 0) -> list[Member]:
    """全時間帯で成立する88人以上の参加者一覧を生成する。"""

    rules = deterministic_rules()
    leaders = list(rules.rally_leaders.values())
    members = [
        Member(
            name=name,
            alliance="未設定",
            tier=Tier.G8 if index < 3 else Tier.G5,
            has_vc=True,
        )
        for index, name in enumerate(leaders)
    ]
    required_count = 88 + extra_member_count - len(members)
    tiers = (Tier.G8, Tier.G7, Tier.G6, Tier.G5)
    members.extend(
        Member(
            name=f"参加者{index:03d}",
            alliance="未設定",
            tier=tiers[index % len(tiers)],
            has_vc=True,
        )
        for index in range(required_count)
    )
    return members


@pytest.fixture(scope="module")
def dynamic_plan():
    """時間のかかる共通の動的編成を1回だけ生成する。"""

    rules = deterministic_rules()
    return TimeSlotTeamOptimizer(rules).optimize(make_dynamic_roster())


def test_optimizer_enforces_capacity_vc_leaders_and_power_each_slot(
    dynamic_plan,
) -> None:
    """全時間帯で人数、VC、集結主、戦力順序を維持する。"""

    rules = default_rules()
    for start in rules.team_master.event_time.slot_starts:
        assignments = {
            label: dynamic_plan.assignment_at(label, start)
            for label in rules.team_labels
        }
        assert all(
            len(assignments[label].members) == 8
            for label in (TeamLabel.A, TeamLabel.B, TeamLabel.C)
        )
        assert all(
            member.has_vc
            for label in (TeamLabel.A, TeamLabel.B, TeamLabel.C)
            for member in assignments[label].members
        )
        for label in rules.team_labels:
            assert rules.rally_leaders[label] in assignments[label].member_names()
        power = {
            label: sum(rules.tier_power[member.tier] for member in assignment.members)
            for label, assignment in assignments.items()
        }
        assert power[TeamLabel.A] > power[TeamLabel.B] >= power[TeamLabel.C]


def test_optimizer_uses_ninth_member_only_outside_priority_teams() -> None:
    """89人目はA〜Cではなく最大9人のチームへ配置する。"""

    rules = deterministic_rules()
    plan = TimeSlotTeamOptimizer(rules).optimize(make_dynamic_roster(1))
    first_slot = rules.team_master.event_time.start_minutes
    counts = {
        label: len(plan.assignment_at(label, first_slot).members)
        for label in rules.team_labels
    }

    assert counts[TeamLabel.A] == counts[TeamLabel.B] == counts[TeamLabel.C] == 8
    assert sum(count == 9 for count in counts.values()) == 1


def test_optimizer_separates_member_with_unknown_start_time() -> None:
    """開始時刻未定者を必須条件へ算入せず待機一覧へ分離する。"""

    rules = deterministic_rules()
    roster = make_dynamic_roster()
    roster.append(
        Member(
            name="時間未定",
            alliance="未設定",
            tier=Tier.G7,
            has_vc=True,
            starts_at_21=False,
        )
    )

    plan = TimeSlotTeamOptimizer(rules).optimize(roster)

    assert tuple(member.name for member in plan.standby_members) == ("時間未定",)


def test_optimizer_rejects_vc_shortage_in_any_time_slot() -> None:
    """途中離脱によりA〜CのVC人数が不足する場合は実行前に拒否する。"""

    rules = deterministic_rules()
    roster = make_dynamic_roster()
    roster = [
        Member(
            name=member.name,
            alliance=member.alliance,
            tier=member.tier,
            has_vc=index < 23,
        )
        for index, member in enumerate(roster)
    ]

    with pytest.raises(OptimizationError, match="VC参加者が不足"):
        TimeSlotTeamOptimizer(rules).optimize(roster)


def test_optimizer_returns_identical_plan_for_same_input(dynamic_plan) -> None:
    """決定的時間で打ち切る単一workerの探索は、同じ入力へ同じ編成を返す。"""

    plan = TimeSlotTeamOptimizer(deterministic_rules()).optimize(make_dynamic_roster())

    assert plan == dynamic_plan


def test_optimizer_reports_timeout_separately_from_infeasibility() -> None:
    """解が見つかる前に探索上限へ達した場合は、時間切れとして報告する。"""

    rules = deterministic_rules(deterministic_time=0.01)

    with pytest.raises(OptimizationTimeoutError, match="時間切れ") as raised:
        TimeSlotTeamOptimizer(rules).optimize(make_dynamic_roster())

    assert isinstance(raised.value, OptimizationError)
    assert not isinstance(raised.value, InfeasibleRosterError)
    assert "編成が存在しないとは確定していません" in str(raised.value)


def test_optimizer_reports_infeasible_roster() -> None:
    """全チームの最大人数を超える参加者は、解が存在しないとして報告する。"""

    rules = deterministic_rules()
    capacity = sum(team.maximum_members for team in rules.team_master.teams)
    roster = make_dynamic_roster(capacity + 1 - 88)

    with pytest.raises(InfeasibleRosterError, match="編成は存在しません") as raised:
        TimeSlotTeamOptimizer(rules).optimize(roster)

    assert isinstance(raised.value, OptimizationError)
    assert not isinstance(raised.value, OptimizationTimeoutError)


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
