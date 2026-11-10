"""生成した所属固定の編成で、独立Validatorの必須条件の判定を検証する性質テスト。

有効な編成を構成的に生成し、必須条件を1つだけ破る変更を加える。Validatorが期待する
コード、隊、時間帯だけを必須条件エラーとして返すことで、見逃しと誤検出の両方を検出する。
"""

from dataclasses import replace

from hypothesis import assume, given
from hypothesis import strategies as st

from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.plan import TeamPlan
from kvk_team.team_building.domain.specification import MemberRef, OperatorSpecification
from kvk_team.team_building.domain.team import (
    EXTENSION_BOUNDARY_MINUTES,
    SORTIE_FLOOR,
    TOP_TEAM_COUNT,
)
from kvk_team.team_building.domain.validation import (
    TeamPlanValidator,
    ValidationCode,
    ValidationIssue,
)
from team_plan_strategies import (
    EVENT,
    MEMBER_CAP,
    RULES,
    SLOT_STARTS,
    PowerTie,
    Scenario,
    covers,
    make_member,
    master_assumption_errors,
    scenarios,
    team_power,
    with_vc,
)

IssueKey = tuple[ValidationCode, int | None, int | None]
"""検証結果1件を、コード、隊の番号、時間帯の開始時刻で表す。"""


def issue_key(issue: ValidationIssue) -> IssueKey:
    """検証結果を比較用のキーへ変換する。"""

    start = issue.time_slot.start_minutes if issue.time_slot is not None else None
    return issue.code, issue.team_number, start


def issue_keys(
    scenario: Scenario,
    plan: TeamPlan,
    specification: OperatorSpecification | None = None,
    source_members: list[Member] | None = None,
) -> set[IssueKey]:
    """変更した編成を検証し、必須条件エラーのキーを返す。"""

    report = TeamPlanValidator(RULES).validate(
        plan,
        scenario.source_members if source_members is None else source_members,
        scenario.specification if specification is None else specification,
    )
    return {issue_key(issue) for issue in report.issues}


def all_slots(code: ValidationCode, number: int | None) -> set[IssueKey]:
    """全時間帯の同じ検証結果のキーを返す。"""

    return {(code, number, start) for start in SLOT_STARTS}


def test_strategies_match_team_master() -> None:
    """生成戦略の前提がチームマスタと一致する。

    失敗した場合はValidatorではなく、`tests/team_plan_strategies.py`の見直しが必要である。
    """

    assert master_assumption_errors() == []


@given(scenarios())
def test_validator_accepts_generated_valid_plan(scenario: Scenario) -> None:
    """必須条件を満たす編成を受理し、8人未満、リーダー不在、延長境界時刻以降の休止を警告する。

    生成した所属と参加時間から、警告が出るべき隊と時間帯が決まる。
    """

    report = TeamPlanValidator(RULES).validate(
        scenario.plan(), scenario.source_members, scenario.specification
    )
    expected: set[IssueKey] = set()
    for number, (leader, members) in enumerate(
        zip(scenario.leaders, scenario.teams, strict=True), start=1
    ):
        if number <= TOP_TEAM_COUNT:
            continue
        for start in SLOT_STARTS:
            count = scenario.present_count(members, start)
            if count == 0:
                expected.add((ValidationCode.REST, number, start))
                continue
            if count < SORTIE_FLOOR:
                expected.add((ValidationCode.UNDERFILLED, number, start))
            if leader not in members or not covers(leader, start):
                expected.add((ValidationCode.LEADER_ABSENT, number, start))

    assert report.issues == ()
    assert {issue_key(warning) for warning in report.warnings} == expected
    assert len(report.warnings) == len(expected)
    assert report.waiting == scenario.waiting
    assert set(report.undecided) == set(scenario.undecided)


@given(scenarios(power_tie=PowerTie.SECOND_EQUALS_THIRD))
def test_validator_accepts_equal_power_of_second_and_third(scenario: Scenario) -> None:
    """第2隊と第3隊の戦力が同じ編成を`>=`の境界として受理する。"""

    assert issue_keys(scenario, scenario.plan()) == set()


@given(scenarios(power_tie=PowerTie.FIRST_EQUALS_SECOND))
def test_validator_rejects_equal_power_of_first_and_second(scenario: Scenario) -> None:
    """第1隊と第2隊の戦力が同じ編成を、全時間帯で`>`を満たさないとして拒否する。"""

    assert issue_keys(scenario, scenario.plan()) == all_slots(
        ValidationCode.POWER_ORDER, None
    )


@given(scenarios(), st.data())
def test_validator_rejects_member_in_two_places(
    scenario: Scenario, data: st.DataObject
) -> None:
    """第4隊以降のメンバーを待機にも置いた編成を重複として拒否する。"""

    candidates = [
        member
        for number, team in enumerate(scenario.teams, start=1)
        if number > TOP_TEAM_COUNT
        for member in team
        if member not in scenario.leaders
    ]
    assume(candidates)
    member = data.draw(st.sampled_from(candidates))
    plan = scenario.plan(waiting=[*scenario.waiting, member])

    assert issue_keys(scenario, plan) == {(ValidationCode.DUPLICATE, None, None)}


@given(scenarios())
def test_validator_rejects_member_neither_in_team_nor_waiting(
    scenario: Scenario,
) -> None:
    """参加時間が確定しているのに隊にも待機にもいない参加者を拒否する。"""

    assume(scenario.waiting)
    plan = scenario.plan(waiting=list(scenario.waiting[1:]))

    assert issue_keys(scenario, plan) == {(ValidationCode.UNASSIGNED, None, None)}


@given(scenarios())
def test_validator_rejects_unknown_member(scenario: Scenario) -> None:
    """参加者一覧にいないメンバーを待機に置いた編成を拒否する。"""

    stranger = make_member("一覧にいない参加者", Tier.G5, has_vc=False)
    plan = scenario.plan(waiting=[*scenario.waiting, stranger])

    assert issue_keys(scenario, plan) == {(ValidationCode.UNEXPECTED, None, None)}


@given(scenarios())
def test_validator_rejects_undecided_member_moved_to_waiting(
    scenario: Scenario,
) -> None:
    """参加時間未定のメンバーを別枠から待機へ移した編成を拒否する（FRM-060）。"""

    movable = [
        member for member in scenario.undecided if member not in scenario.leaders
    ]
    assume(movable)
    member = movable[0]
    plan = scenario.plan(
        waiting=[*scenario.waiting, member],
        undecided=[item for item in scenario.undecided if item != member],
    )

    assert issue_keys(scenario, plan) == {
        (ValidationCode.UNEXPECTED, None, None),
        (ValidationCode.UNASSIGNED, None, None),
    }


@given(scenarios())
def test_validator_rejects_confirmed_member_in_undecided(scenario: Scenario) -> None:
    """参加時間が確定しているメンバーを別枠に置いた編成を拒否する。"""

    assume(scenario.waiting)
    member = scenario.waiting[0]
    plan = scenario.plan(
        waiting=list(scenario.waiting[1:]),
        undecided=[*scenario.undecided, member],
    )

    # 別枠へ移したメンバーは、隊にも待機にもいない確定参加者にも当たる。
    assert issue_keys(scenario, plan) == {
        (ValidationCode.UNEXPECTED, None, None),
        (ValidationCode.UNASSIGNED, None, None),
    }


@given(scenarios(), st.integers(min_value=1, max_value=TOP_TEAM_COUNT))
def test_validator_rejects_top_team_above_size(scenario: Scenario, number: int) -> None:
    """上位隊へ全時間帯に参加するVC可能な9人目を置いた編成を人数違反として拒否する。"""

    extra = make_member("9人目", Tier.G5, has_vc=True)
    teams = scenario.copy_teams()
    teams[number - 1].append(extra)
    source = [*scenario.source_members, extra]
    keys = issue_keys(scenario, scenario.plan(teams), source_members=source)

    # 9人目で戦力が増えるため、上の隊との戦力関係が崩れることがある。
    assert all_slots(ValidationCode.TOP_TEAM_SIZE, number) <= keys
    assert {key[0] for key in keys} <= {
        ValidationCode.TOP_TEAM_SIZE,
        ValidationCode.POWER_ORDER,
    }


@given(scenarios(), st.integers(min_value=1, max_value=TOP_TEAM_COUNT))
def test_validator_rejects_top_team_below_size(scenario: Scenario, number: int) -> None:
    """上位隊の1人を待機へ移した編成を、第4隊以降と違い警告ではなく人数違反として拒否する。"""

    teams = scenario.copy_teams()
    removed = teams[number - 1].pop()
    keys = issue_keys(
        scenario, scenario.plan(teams, waiting=[*scenario.waiting, removed])
    )

    assert all_slots(ValidationCode.TOP_TEAM_SIZE, number) <= keys
    assert {key[0] for key in keys} <= {
        ValidationCode.TOP_TEAM_SIZE,
        ValidationCode.POWER_ORDER,
    }


@given(scenarios())
def test_validator_rejects_flexible_team_above_cap(scenario: Scenario) -> None:
    """第4隊以降へ上限を超えて置いた編成を、全時間帯の人数違反として拒否する。"""

    assume(len(scenario.teams) > TOP_TEAM_COUNT)
    number = TOP_TEAM_COUNT + 1
    extras = [
        make_member(f"追加参加者{index}", Tier.G5, has_vc=False)
        for index in range(MEMBER_CAP + 1)
    ]
    teams = scenario.copy_teams()
    teams[number - 1].extend(extras)
    source = [*scenario.source_members, *extras]

    keys = issue_keys(scenario, scenario.plan(teams), source_members=source)

    assert keys == all_slots(ValidationCode.CAPACITY, number)


@given(scenarios(), st.integers(min_value=1, max_value=TOP_TEAM_COUNT), st.data())
def test_validator_rejects_non_vc_member_in_top_team(
    scenario: Scenario, number: int, data: st.DataObject
) -> None:
    """上位隊のメンバーをVC不可へ変えた編成を拒否する（FRM-021）。"""

    teams = scenario.copy_teams()
    index = data.draw(st.integers(min_value=1, max_value=len(teams[number - 1]) - 1))
    original = teams[number - 1][index]
    changed = with_vc(original, False)
    teams[number - 1][index] = changed
    source = [
        changed if member == original else member for member in scenario.source_members
    ]

    assert issue_keys(scenario, scenario.plan(teams), source_members=source) == {
        (ValidationCode.VC_REQUIRED, number, None)
    }


@given(scenarios())
def test_validator_rejects_leader_outside_own_team(scenario: Scenario) -> None:
    """第4隊のリーダーを第5隊へ移した編成を拒否する（FRM-002）。"""

    assume(len(scenario.teams) > TOP_TEAM_COUNT + 1)
    number = TOP_TEAM_COUNT + 1
    leader = scenario.leaders[number - 1]
    teams = scenario.copy_teams()
    assume(leader in teams[number - 1])
    teams[number - 1].remove(leader)
    teams[number].append(leader)
    assume(len(teams[number]) <= MEMBER_CAP)
    keys = issue_keys(scenario, scenario.plan(teams))

    assert (ValidationCode.LEADER, number, None) in keys
    assert {key[0] for key in keys} <= {
        ValidationCode.LEADER,
        ValidationCode.REST,
    }


@given(scenarios())
def test_validator_rejects_wrong_team_count(scenario: Scenario) -> None:
    """リーダーの人数と隊の数が合わない編成を拒否する（FRM-001）。"""

    extra_leader = scenario.waiting[0] if scenario.waiting else None
    assume(extra_leader is not None)
    assert extra_leader is not None
    specification = OperatorSpecification(
        leaders=(
            *scenario.specification.leaders,
            MemberRef(extra_leader.name, extra_leader.alliance),
        )
    )

    assert issue_keys(scenario, scenario.plan(), specification=specification) == {
        (ValidationCode.TEAMS, None, None)
    }


@given(scenarios())
def test_validator_rejects_swapped_leaders(scenario: Scenario) -> None:
    """リーダー一覧の順と違うリーダーの隊を拒否する。"""

    first, second, *rest = scenario.specification.leaders
    specification = OperatorSpecification(leaders=(second, first, *rest))

    assert issue_keys(scenario, scenario.plan(), specification=specification) == {
        (ValidationCode.LEADER, 1, None),
        (ValidationCode.LEADER, 2, None),
    }


@given(scenarios())
def test_validator_rejects_broken_power_order(scenario: Scenario) -> None:
    """第1隊と第2隊のリーダー以外を入れ替え、戦力関係が崩れた編成を拒否する。"""

    teams = scenario.copy_teams()
    assume(team_power(teams[0]) > team_power(teams[1]))
    teams[0][1:], teams[1][1:] = teams[1][1:], teams[0][1:]
    assume(team_power(teams[0]) <= team_power(teams[1]))

    keys = issue_keys(scenario, scenario.plan(teams))

    assert all_slots(ValidationCode.POWER_ORDER, None) <= keys
    assert {key[0] for key in keys} == {ValidationCode.POWER_ORDER}


@given(scenarios(), st.data())
def test_validator_reports_rest_before_boundary_as_shortfall(
    scenario: Scenario, data: st.DataObject
) -> None:
    """延長境界時刻より前に所属メンバーが0人になる隊を、下限の不足として拒否する（FRM-048）。

    第4隊以降の所属をリーダーだけにし、そのリーダーを延長境界時刻より前の途中から参加させる。
    """

    assume(len(scenario.teams) > TOP_TEAM_COUNT)
    number = TOP_TEAM_COUNT + 1
    leader = scenario.leaders[number - 1]
    assume(leader in scenario.teams[number - 1])
    late_start = data.draw(
        st.sampled_from(
            [start for start in SLOT_STARTS[1:] if start < EXTENSION_BOUNDARY_MINUTES]
        )
    )
    late_leader = replace(
        leader, starts_at_21=False, start_time_minutes=late_start, end_time_minutes=None
    )
    others = [member for member in scenario.teams[number - 1] if member != leader]
    teams = scenario.copy_teams()
    teams[number - 1] = [late_leader]
    source = [
        late_leader if member == leader else member
        for member in scenario.source_members
    ]
    leaders = tuple(
        late_leader if item == leader else item for item in scenario.leaders
    )
    modified = replace(scenario, leaders=leaders)
    plan = modified.plan(teams, waiting=[*scenario.waiting, *others])

    report = TeamPlanValidator(RULES).validate(plan, source, modified.specification)

    expected_rest = {
        (ValidationCode.REST, number, start)
        for start in SLOT_STARTS
        if start < late_start
    }
    assert {issue_key(issue) for issue in report.issues} == expected_rest
    assert report.has_only_shortfalls
    assert {issue_key(issue) for issue in report.shortfalls} == expected_rest


@given(scenarios(), st.integers(min_value=1, max_value=TOP_TEAM_COUNT), st.data())
def test_validator_rejects_top_team_member_swapped_mid_battle(
    scenario: Scenario, number: int, data: st.DataObject
) -> None:
    """上位隊の1人を、途中で抜ける人と途中から来る人の2人に置き換えた所属を拒否する。

    どの時間帯も8人で戦力も同じになるが、全時間帯で入れ替えない規則（FRM-020〜FRM-022）に反する。
    """

    teams = scenario.copy_teams()
    index = data.draw(st.integers(min_value=1, max_value=len(teams[number - 1]) - 1))
    removed = teams[number - 1].pop(index)
    switch = data.draw(st.sampled_from(SLOT_STARTS[1:]))
    leaving = make_member(
        "途中で抜ける人", removed.tier, True, (SLOT_STARTS[0], switch)
    )
    joining = make_member(
        "途中から来る人", removed.tier, True, (switch, EVENT.end_minutes)
    )
    teams[number - 1].extend((leaving, joining))
    source = [
        *(member for member in scenario.source_members if member != removed),
        leaving,
        joining,
    ]

    assert issue_keys(scenario, scenario.plan(teams), source_members=source) == {
        (ValidationCode.TOP_TEAM_SIZE, number, None),
        (ValidationCode.TOP_TEAM_ALWAYS, number, None),
    }


def _fixed_scenario(fourth_leader_end: int | None = None) -> Scenario:
    """上位隊の戦力が第1隊 > 第2隊 > 第3隊になる、決め打ちの4〜5隊の編成を作る。"""

    top_tiers = (Tier.G8, Tier.G7, Tier.G6)
    teams: list[tuple[Member, ...]] = []
    leaders: list[Member] = []
    for number, tier in enumerate(top_tiers, start=1):
        leader = make_member(f"第{number}隊リーダー", Tier.G8, True)
        others = tuple(
            make_member(f"第{number}隊参加者{index}", tier, True)
            for index in range(1, 8)
        )
        teams.append((leader, *others))
        leaders.append(leader)
    window = None if fourth_leader_end is None else (SLOT_STARTS[0], fourth_leader_end)
    fourth = make_member("第4隊リーダー", Tier.G5, False, window)
    fifth = make_member("第5隊リーダー", Tier.G5, False)
    teams.extend(((fourth,), (fifth,)))
    leaders.extend((fourth, fifth))
    return Scenario(
        teams=tuple(teams), leaders=tuple(leaders), waiting=(), undecided=()
    )


def test_fixed_scenario_is_valid() -> None:
    """決め打ちの編成そのものは必須条件を満たす。以下のテストの前提を確かめる。"""

    scenario = _fixed_scenario()

    assert issue_keys(scenario, scenario.plan()) == set()


def test_validator_rejects_second_team_weaker_than_third() -> None:
    """第2隊と第3隊のリーダー以外を入れ替え、第2隊 >= 第3隊が崩れた編成を拒否する。"""

    scenario = _fixed_scenario()
    teams = scenario.copy_teams()
    teams[1][1:], teams[2][1:] = teams[2][1:], teams[1][1:]

    assert issue_keys(scenario, scenario.plan(teams)) == all_slots(
        ValidationCode.POWER_ORDER, None
    )


def test_validator_rejects_member_in_two_teams() -> None:
    """第4隊のリーダーを第5隊にも置いた編成を、2つの隊への重複として拒否する（FRM-010）。"""

    scenario = _fixed_scenario()
    teams = scenario.copy_teams()
    teams[4].append(scenario.leaders[3])

    assert issue_keys(scenario, scenario.plan(teams)) == {
        (ValidationCode.DUPLICATE, None, None)
    }


def test_validator_treats_rest_from_23_30_as_shortfall_until_boundary() -> None:
    """23:30から所属メンバーが0人になる隊は、23:30の休止をエラー、24:00以降を警告にする。"""

    scenario = _fixed_scenario(fourth_leader_end=23 * 60 + 30)

    report = TeamPlanValidator(RULES).validate(
        scenario.plan(), scenario.source_members, scenario.specification
    )

    assert {issue_key(issue) for issue in report.issues} == {
        (ValidationCode.REST, 4, 23 * 60 + 30)
    }
    assert {
        issue_key(warning)
        for warning in report.warnings
        if warning.code is ValidationCode.REST
    } == {(ValidationCode.REST, 4, 24 * 60), (ValidationCode.REST, 4, 24 * 60 + 30)}


def test_validator_treats_rest_from_boundary_as_warning() -> None:
    """24:00から所属メンバーが0人になる隊は、休止を警告だけにして受理する（FRM-043、FRM-048）。"""

    scenario = _fixed_scenario(fourth_leader_end=24 * 60)

    report = TeamPlanValidator(RULES).validate(
        scenario.plan(), scenario.source_members, scenario.specification
    )

    assert report.issues == ()
    assert {
        issue_key(warning)
        for warning in report.warnings
        if warning.code is ValidationCode.REST
    } == {(ValidationCode.REST, 4, 24 * 60), (ValidationCode.REST, 4, 24 * 60 + 30)}
