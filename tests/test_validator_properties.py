"""生成した編成で、独立Validatorの必須条件の判定を検証する性質テスト。

有効な編成を構成的に生成し、必須条件を1つだけ破る変更を加える。Validatorが期待する
コード、チーム、時間帯だけを必須条件エラーとして返すことで、見逃しと誤検出の両方を
検出する。
"""

from hypothesis import assume, given
from hypothesis import strategies as st

from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.team import TeamLabel
from kvk_team.team_building.domain.validation import (
    DynamicTeamValidator,
    DynamicValidationCode,
    DynamicValidationIssue,
)
from team_plan_strategies import (
    FIXED_TEAM_SIZE,
    FIXED_TEAMS,
    FLEXIBLE_TEAMS,
    MASTER,
    RULES,
    SLOT_STARTS,
    PowerTie,
    Roster,
    Scenario,
    master_assumption_errors,
    scenarios,
    team_power,
)

LEADER_NAMES = frozenset(
    name
    for definition in MASTER.teams
    for name in (definition.rally_leader, *definition.substitute_leaders)
)
slot_starts = st.sampled_from(SLOT_STARTS)


IssueKey = tuple[DynamicValidationCode, TeamLabel | None, int | None]
"""検証結果1件を、コード、チーム、時間帯の開始時刻で表す。"""


def issue_key(issue: DynamicValidationIssue) -> IssueKey:
    """検証結果を比較用のキーへ変換する。"""

    start = issue.time_slot.start_minutes if issue.time_slot is not None else None
    return issue.code, issue.team_label, start


def issue_keys(scenario: Scenario, roster: Roster) -> set[IssueKey]:
    """変更した配置を検証し、必須条件エラーのキーを返す。"""

    report = DynamicTeamValidator(RULES).validate(
        scenario.plan(roster),
        scenario.source_members,
    )
    return {issue_key(issue) for issue in report.issues}


def non_leaders(
    teams: dict[TeamLabel, list[Member]],
    labels: tuple[TeamLabel, ...],
) -> list[tuple[TeamLabel, Member]]:
    """指定チームに配置された、集結主と代理以外のメンバーを返す。"""

    return [
        (label, member)
        for label in labels
        for member in teams[label]
        if member.name not in LEADER_NAMES
    ]


def flexible_with_room(
    teams: dict[TeamLabel, list[Member]],
    excluded: TeamLabel | None = None,
) -> list[TeamLabel]:
    """最大人数に達していないD〜Kのチームを返す。"""

    return [
        label
        for label in FLEXIBLE_TEAMS
        if label is not excluded
        and len(teams[label]) < MASTER.teams_by_label[label].maximum_members
    ]


def expected_leader(members: list[Member], label: TeamLabel) -> Member | None:
    """有効な配置で、そのチームが置くべき集結主または代理を返す。"""

    definition = MASTER.teams_by_label[label]
    by_name = {member.name: member for member in members}
    for name in (definition.rally_leader, *definition.substitute_leaders):
        if name in by_name:
            return by_name[name]
    return None


def test_strategies_match_team_master() -> None:
    """生成戦略の前提がチームマスタと一致する。

    失敗した場合はValidatorではなく、`tests/team_plan_strategies.py`の見直しが必要である。
    """

    assert master_assumption_errors() == []


@given(scenarios())
def test_validator_accepts_generated_valid_plan(scenario: Scenario) -> None:
    """必須条件を満たす編成を受理し、D〜Kの不足と到着待ちを該当箇所すべてで警告する。

    生成した配置では参加中のメンバーが全員自チームにいるため、チームの人数と集結主の有無から
    警告が出るべきチームと時間帯が決まる。
    """

    report = DynamicTeamValidator(RULES).validate(
        scenario.plan(),
        scenario.source_members,
    )
    expected_warnings = {
        (DynamicValidationCode.UNDERFILLED, label, start)
        for start in SLOT_STARTS
        for label in FLEXIBLE_TEAMS
        if len(scenario.roster[start][label])
        < MASTER.teams_by_label[label].minimum_members
    } | {
        (DynamicValidationCode.RALLY_LEADER, label, start)
        for start in SLOT_STARTS
        for label in MASTER.team_labels
        if expected_leader(list(scenario.roster[start][label]), label) is None
    }

    assert report.issues == ()
    assert {issue_key(warning) for warning in report.warnings} == expected_warnings
    assert len(report.warnings) == len(expected_warnings)
    assert set(report.standby_members) == set(scenario.standby)


@given(scenarios(power_tie=PowerTie.B_EQUALS_C))
def test_validator_accepts_equal_power_of_b_and_c(scenario: Scenario) -> None:
    """BとCの戦力が同じ編成を`B >= C`の境界として受理する。"""

    assert issue_keys(scenario, scenario.copy_roster()) == set()


@given(scenarios(power_tie=PowerTie.A_EQUALS_B))
def test_validator_rejects_equal_power_of_a_and_b(scenario: Scenario) -> None:
    """AとBの戦力が同じ編成を、全時間帯で`A > B`を満たさないとして拒否する。"""

    assert issue_keys(scenario, scenario.copy_roster()) == {
        (DynamicValidationCode.POWER_ORDER, None, start) for start in SLOT_STARTS
    }


@given(scenarios(), slot_starts, st.data())
def test_validator_rejects_member_assigned_twice(
    scenario: Scenario,
    start: int,
    data: st.DataObject,
) -> None:
    """同じ時間帯に2チームへ置いた参加者を重複配置として拒否する。"""

    roster = scenario.copy_roster()
    teams = roster[start]
    source, member = data.draw(
        st.sampled_from(
            [(label, m) for label in MASTER.team_labels for m in teams[label]]
        )
    )
    targets = flexible_with_room(teams, excluded=source)
    assume(targets)
    teams[data.draw(st.sampled_from(targets))].append(member)

    assert issue_keys(scenario, roster) == {
        (DynamicValidationCode.DUPLICATE, None, start)
    }


@given(scenarios(), slot_starts, st.data())
def test_validator_rejects_unassigned_active_member(
    scenario: Scenario,
    start: int,
    data: st.DataObject,
) -> None:
    """参加中なのにどのチームにもいない参加者を未配置として拒否する。"""

    roster = scenario.copy_roster()
    teams = roster[start]
    candidates = non_leaders(teams, FLEXIBLE_TEAMS)
    assume(candidates)
    label, member = data.draw(st.sampled_from(candidates))
    teams[label].remove(member)

    assert issue_keys(scenario, roster) == {
        (DynamicValidationCode.UNASSIGNED, None, start)
    }


@given(scenarios(), slot_starts, st.data())
def test_validator_rejects_member_outside_participation_time(
    scenario: Scenario,
    start: int,
    data: st.DataObject,
) -> None:
    """待機、参加時間外、入力にない参加者の配置を拒否する。"""

    roster = scenario.copy_roster()
    teams = roster[start]
    placed = {member for members in teams.values() for member in members}
    outsiders = [
        *scenario.standby,
        *(member for member in scenario.members if member not in placed),
        Member(name="入力にない参加者", alliance="検証同盟", tier=Tier.G5),
    ]
    targets = flexible_with_room(teams)
    assume(targets)
    teams[data.draw(st.sampled_from(targets))].append(
        data.draw(st.sampled_from(outsiders))
    )

    assert issue_keys(scenario, roster) == {
        (DynamicValidationCode.UNEXPECTED, None, start)
    }


@given(scenarios(), slot_starts, st.data())
def test_validator_rejects_fixed_team_above_size(
    scenario: Scenario,
    start: int,
    data: st.DataObject,
) -> None:
    """Aへ9人目を置いた編成を人数違反として拒否する。"""

    roster = scenario.copy_roster()
    teams = roster[start]
    candidates = [
        (label, member)
        for label, member in non_leaders(teams, FLEXIBLE_TEAMS)
        if member.has_vc
    ]
    assume(candidates)
    label, member = data.draw(st.sampled_from(candidates))
    teams[label].remove(member)
    teams[TeamLabel.A].append(member)

    assert issue_keys(scenario, roster) == {
        (DynamicValidationCode.CAPACITY, TeamLabel.A, start)
    }


@given(scenarios(), slot_starts, st.data())
def test_validator_rejects_fixed_team_below_size(
    scenario: Scenario,
    start: int,
    data: st.DataObject,
) -> None:
    """Cを7人にした編成を、D〜Kと違い警告ではなく人数違反として拒否する。"""

    roster = scenario.copy_roster()
    teams = roster[start]
    targets = flexible_with_room(teams)
    assume(targets)
    _, member = data.draw(st.sampled_from(non_leaders(teams, (TeamLabel.C,))))
    teams[TeamLabel.C].remove(member)
    teams[data.draw(st.sampled_from(targets))].append(member)

    assert issue_keys(scenario, roster) == {
        (DynamicValidationCode.CAPACITY, TeamLabel.C, start)
    }


@given(scenarios(), slot_starts, st.data())
def test_validator_rejects_flexible_team_above_maximum(
    scenario: Scenario,
    start: int,
    data: st.DataObject,
) -> None:
    """D〜Kへ最大人数を超えて置いた編成を人数違反として拒否する。"""

    roster = scenario.copy_roster()
    teams = roster[start]
    target = data.draw(st.sampled_from(FLEXIBLE_TEAMS))
    others = tuple(label for label in FLEXIBLE_TEAMS if label is not target)
    needed = MASTER.teams_by_label[target].maximum_members + 1 - len(teams[target])
    donors = non_leaders(teams, others)
    assume(len(donors) >= needed)
    for label, member in data.draw(st.permutations(donors))[:needed]:
        teams[label].remove(member)
        teams[target].append(member)

    assert issue_keys(scenario, roster) == {
        (DynamicValidationCode.CAPACITY, target, start)
    }


@given(scenarios(), slot_starts, st.data())
def test_validator_rejects_non_vc_member_in_fixed_team(
    scenario: Scenario,
    start: int,
    data: st.DataObject,
) -> None:
    """A〜CのメンバーをVC不可の同Tierと入れ替えた編成を拒否する。"""

    roster = scenario.copy_roster()
    teams = roster[start]
    pairs = [
        (fixed, fixed_member, flexible, flexible_member)
        for fixed, fixed_member in non_leaders(teams, FIXED_TEAMS)
        for flexible, flexible_member in non_leaders(teams, FLEXIBLE_TEAMS)
        if not flexible_member.has_vc and flexible_member.tier is fixed_member.tier
    ]
    assume(pairs)
    fixed, fixed_member, flexible, flexible_member = data.draw(st.sampled_from(pairs))
    teams[fixed].remove(fixed_member)
    teams[fixed].append(flexible_member)
    teams[flexible].remove(flexible_member)
    teams[flexible].append(fixed_member)

    assert issue_keys(scenario, roster) == {
        (DynamicValidationCode.VC_REQUIRED, fixed, start)
    }


@given(scenarios(), slot_starts, st.data())
def test_validator_rejects_active_leader_outside_own_team(
    scenario: Scenario,
    start: int,
    data: st.DataObject,
) -> None:
    """参加中の集結主または代理を別チームへ移した編成を拒否する。

    人数、VC、戦力が変わらないよう、同じTierのメンバーと入れ替える。
    """

    roster = scenario.copy_roster()
    teams = roster[start]
    pairs = []
    for label in MASTER.team_labels:
        leader = expected_leader(teams[label], label)
        if leader is None:
            continue
        for other_label, other in non_leaders(teams, MASTER.team_labels):
            needs_vc = label in FIXED_TEAMS or other_label in FIXED_TEAMS
            if (
                other_label is not label
                and other.tier is leader.tier
                and (not needs_vc or (leader.has_vc and other.has_vc))
            ):
                pairs.append((label, leader, other_label, other))
    assume(pairs)
    label, leader, other_label, other = data.draw(st.sampled_from(pairs))
    teams[label].remove(leader)
    teams[label].append(other)
    teams[other_label].remove(other)
    teams[other_label].append(leader)

    assert issue_keys(scenario, roster) == {
        (DynamicValidationCode.RALLY_LEADER, label, start)
    }


@given(scenarios(), slot_starts, st.data())
def test_validator_rejects_broken_power_order(
    scenario: Scenario,
    start: int,
    data: st.DataObject,
) -> None:
    """A〜Cの集結主以外を入れ替え、A > B >= Cが崩れた編成を拒否する。"""

    roster = scenario.copy_roster()
    teams = roster[start]
    first, second = data.draw(
        st.sampled_from(
            [
                (TeamLabel.A, TeamLabel.B),
                (TeamLabel.B, TeamLabel.C),
                (TeamLabel.A, TeamLabel.C),
            ]
        )
    )
    first_leader, *first_rest = teams[first]
    second_leader, *second_rest = teams[second]
    teams[first] = [first_leader, *second_rest]
    teams[second] = [second_leader, *first_rest]
    power = {label: team_power(teams[label]) for label in FIXED_TEAMS}
    assume(
        not (
            power[TeamLabel.A] > power[TeamLabel.B]
            and power[TeamLabel.B] >= power[TeamLabel.C]
        )
    )

    assert len(teams[first]) == len(teams[second]) == FIXED_TEAM_SIZE
    assert issue_keys(scenario, roster) == {
        (DynamicValidationCode.POWER_ORDER, None, start)
    }
