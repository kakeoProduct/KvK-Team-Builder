"""回答を確かめる手順のテスト（旧Q-092、作成者の仮定A-10、A-41、ADR 0035）。

架空の世界（`answer_world`）で、受け入れ、使わなかった注記、受け入れなかった注記、番号付きの質問、
時間切れと解なしの区別を確かめる。
"""

from dataclasses import dataclass

import pytest

from answer_world import (
    EARLY_MEMBERS,
    H21,
    H22,
    H23,
    H2130,
    MEMBERS,
    RULES,
    SPECIFICATION,
    World,
    WorldOptimizer,
    WorldValidator,
    answer,
    run,
    use_case,
)
from kvk_team.team_building.adapters.optimization.errors import (
    OptimizationTimeoutError,
)
from kvk_team.team_building.application.build_team_plan import (
    BuildError,
    BuildTeamPlan,
    LowerBoundShortfallError,
    NoValidPlanError,
    ShortfallUndeterminedError,
)
from kvk_team.team_building.application.ports import SearchTimeoutError
from kvk_team.team_building.domain.answers import Answer
from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.specification import (
    LateStart,
    MemberRef,
    SpecificationError,
    SupportRef,
)
from kvk_team.team_building.domain.validation import (
    ValidatedTeamPlan,
    ValidationCode,
    ValidationIssue,
    ValidationReport,
)

H2230 = H22 + 30


def _questions(result: object) -> list[tuple[int, int, tuple[int, ...], bool]]:
    assert isinstance(result, LowerBoundShortfallError), result
    return [
        (
            question.number,
            question.team_number,
            tuple(slot.start_minutes for slot in question.time_slots),
            question.answerable,
        )
        for question in result.questions
    ]


def test_shortfalls_without_answers_become_numbered_questions() -> None:
    """不足は隊と序盤かどうかでまとめ、番号を付けた問いにする（FRM-075、FRM-090）。"""

    world = World(base=frozenset({(7, H21), (7, H2130), (5, H23), (7, H23)}))

    result = run(world, [])

    assert _questions(result) == [
        (1, 5, (H23,), False),
        (2, 7, (H21, H2130), True),
        (3, 7, (H23,), False),
    ]
    assert result.notes == ()


def test_answer_that_resolves_target_is_accepted_and_plan_is_output() -> None:
    """対象の不足をなくし、新しい不足を生まない回答を受け入れて出力する。"""

    world = World(base=frozenset({(7, H21)}), resolves={10: frozenset({(7, H21)})})
    build, optimizer = use_case(world)

    result = build.execute(MEMBERS, SPECIFICATION, [answer((7, H21), 10)])

    assert isinstance(result, ValidatedTeamPlan)
    assert result.notes == ()
    # 回答なしの判定に使う編成と、対象の休止だけを許さない確認の2回で決まる。
    assert optimizer.calls == [(frozenset(), None), (frozenset({10}), frozenset())]


def test_answer_whose_target_is_not_short_is_noted_as_unused() -> None:
    """対象の（隊、時間帯）が下限を満たしていれば、回答を使わずに注記する（FRM-090の性質(3)）。"""

    world = World(base=frozenset())

    result = run(world, [answer((7, H21), 10)])

    assert isinstance(result, ValidatedTeamPlan)
    assert len(result.notes) == 1
    assert "第7隊 21:00への回答" in result.notes[0]
    assert "使いませんでした" in result.notes[0]


def test_answer_resolved_by_earlier_accepted_answer_is_noted_as_unused() -> None:
    """ほかの受け入れた回答で下限を満たした対象への回答は、使わなかったと注記する。"""

    both = frozenset({(7, H21), (8, H21)})
    world = World(base=both, resolves={9: both})

    result = run(world, [answer((8, H21), 10), answer((7, H21), 9)])

    assert isinstance(result, ValidatedTeamPlan)
    assert len(result.notes) == 1
    assert "第8隊 21:00への回答" in result.notes[0]
    assert "使いませんでした" in result.notes[0]


@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_answers_accept_lower_target_first_regardless_of_order(
    reverse: bool,
) -> None:
    """同時に成り立たない回答は、対象の隊の番号の順に受け入れる（作成者の仮定A-10の例2）。"""

    world = World(
        base=frozenset({(7, H21), (8, H21)}),
        resolves={9: frozenset({(7, H21)}), 10: frozenset({(8, H21)})},
        conflicts=frozenset({frozenset({9, 10})}),
    )
    answers = [answer((7, H21), 9), answer((8, H21), 10)]

    result = run(world, list(reversed(answers)) if reverse else answers)

    assert _questions(result) == [(1, 8, (H21,), True)]
    assert len(result.notes) == 1
    assert "第8隊 21:00への回答" in result.notes[0]
    assert "受け入れませんでした" in result.notes[0]


def test_answer_creating_new_shortfall_is_not_accepted() -> None:
    """判定に使う編成と比べて新しく不足を生む回答は受け入れない（FRM-090）。"""

    world = World(
        base=frozenset({(7, H21)}),
        resolves={10: frozenset({(7, H21)})},
        creates={10: frozenset({(5, H2130)})},
    )

    result = run(world, [answer((7, H21), 10)])

    assert _questions(result) == [(1, 7, (H21,), True)]
    assert "休止を新しく生まない" in result.notes[0]


def test_answer_to_target_outside_opening_is_input_error() -> None:
    """序盤以外の対象への回答は、ほかの指定で変わらない誤りとして入力のエラーにする。

    遅れて出撃させる案は序盤の選択肢で（FRM-041）、序盤以外の問いにはこの版では答えられない
    （利用者の決定、2026-11-10。FRM-047、作成者の仮定A-41）。
    """

    world = World(base=frozenset({(8, H23)}), resolves={10: frozenset({(8, H23)})})
    build, optimizer = use_case(world)

    with pytest.raises(SpecificationError, match="序盤"):
        build.execute(MEMBERS, SPECIFICATION, [answer((8, H23), 10)])
    assert optimizer.calls == []


def test_second_start_for_same_team_is_not_accepted() -> None:
    """先に受け入れた回答と同じ隊の別の出撃開始時刻は受け入れない。"""

    world = World(
        base=frozenset({(7, H21), (8, H21)}),
        resolves={10: frozenset({(7, H21)})},
    )

    result = run(world, [answer((7, H21), 10), answer((8, H21), 10, start=H2230)])

    assert _questions(result) == [(1, 8, (H21,), True)]
    assert "同じ隊を遅れて出撃させる別の指定" in result.notes[0]


def test_same_team_and_start_with_other_supports_is_not_accepted() -> None:
    """同じ隊と出撃開始時刻でも、応援が違う指定は別の指定として受け入れない（作成者の仮定A-41）。"""

    world = World(
        base=frozenset({(7, H21), (8, H21)}),
        resolves={10: frozenset({(7, H21)})},
    )
    first, second = EARLY_MEMBERS
    answers = [
        Answer(7, H21, LateStart(10, H22, _supports(first, 7))),
        Answer(8, H21, LateStart(10, H22, _supports(second, 8))),
    ]

    result = run(world, answers)

    assert _questions(result) == [(1, 8, (H21,), True)]
    assert len(result.notes) == 1
    assert "第8隊 21:00への回答" in result.notes[0]
    assert "同じ隊を遅れて出撃させる別の指定" in result.notes[0]


def _supports(member: Member, team: int) -> tuple[SupportRef, ...]:
    return tuple(
        SupportRef(MemberRef(member.name, member.alliance), slot, team)
        for slot in (H21, H2130)
    )


def test_late_team_own_pre_start_slots_are_resolved_without_note() -> None:
    """自分の隊を遅らせて直った対象には、使わなかった注記を付けない（FRM-090の性質(3)）。"""

    world = World(base=frozenset({(10, H21), (10, H2130)}))

    result = run(world, [answer((10, H21), 10), answer((10, H2130), 10)])

    assert isinstance(result, ValidatedTeamPlan)
    # 2件目は1件目と同じ指定で、その指定そのもので直ったため注記しない。
    assert result.notes == ()


def test_invalid_answer_is_input_error_before_optimizing() -> None:
    """ほかの指定で変わらない誤りは、最適化の前に入力のエラーにする（FRM-047）。"""

    world = World(base=frozenset({(7, H21)}))
    build, optimizer = use_case(world)

    with pytest.raises(SpecificationError, match="第1〜3隊"):
        build.execute(MEMBERS, SPECIFICATION, [answer((7, H21), 2)])
    assert optimizer.calls == []


def test_unproven_judgment_plan_is_timeout() -> None:
    """判定に使う編成の最適性を示せなければ、時間切れのエラーとする（FRM-090の性質(6)）。"""

    world = World(base=frozenset({(7, H21)}), optimal_without_answers=False)

    result = run(world, [answer((7, H21), 10)])

    assert isinstance(result, ShortfallUndeterminedError)
    assert isinstance(result, SearchTimeoutError)


def test_unproven_plan_after_accepting_answer_with_remaining_shortfall_is_timeout() -> (
    None
):
    """受け入れた後の編成に不足が残り、最適性を示せなければ時間切れのエラーとする。"""

    world = World(
        base=frozenset({(7, H21), (8, H21)}),
        resolves={10: frozenset({(7, H21)})},
        optimal_with_answers=False,
    )

    result = run(world, [answer((7, H21), 10)])

    assert isinstance(result, ShortfallUndeterminedError)


def test_unproven_trial_with_remaining_shortfall_is_timeout_before_next_answer() -> (
    None
):
    """回答を確かめた編成に不足が残り、最適性を示せなければ、次の回答へ進まずに時間切れとする。

    その編成を基準にすると、後の回答の判定と問いが最適でない編成に左右される（FRM-090の性質(6)）。
    """

    world = World(
        base=frozenset({(7, H21), (8, H21)}),
        resolves={9: frozenset({(7, H21)}), 10: frozenset({(8, H21)})},
        unproven=frozenset({frozenset({9})}),
    )
    build, optimizer = use_case(world)

    with pytest.raises(ShortfallUndeterminedError):
        build.execute(
            MEMBERS, SPECIFICATION, [answer((7, H21), 9), answer((8, H21), 10)]
        )
    # 第9隊を遅らせた確認で止まり、第10隊を加える確認へ進まない。
    assert optimizer.calls[-1][0] == frozenset({9})


def test_unproven_plan_without_shortfall_is_output() -> None:
    """最適性を示せなくても不足がなければ出力し、最適性を示せなかったことを残す（FRM-049）。"""

    world = World(
        base=frozenset({(7, H21)}),
        resolves={10: frozenset({(7, H21)})},
        optimal_with_answers=False,
    )

    result = run(world, [answer((7, H21), 10)])

    assert isinstance(result, ValidatedTeamPlan)
    assert result.proven_optimal is False


def test_infeasible_judgment_plan_stops_with_reason_even_with_answers() -> None:
    """選択肢で解消できない必須条件の違反は、理由を示して止める（FRM-090の性質(2)）。"""

    world = World(base=frozenset(), infeasible=True)

    result = run(world, [answer((7, H21), 10)])

    assert isinstance(result, NoValidPlanError)


@dataclass
class TimeoutOnTrialOptimizer(WorldOptimizer):
    """回答を加えた確認でだけ時間切れを送出する。"""

    def optimize(self, members, specification, allowed_shortfalls=None):  # type: ignore[no-untyped-def]
        if specification.late_starts:
            self.calls.append((frozenset({-1}), allowed_shortfalls))
            raise OptimizationTimeoutError("時間切れ")
        return super().optimize(members, specification, allowed_shortfalls)


@dataclass
class FlakyTrialValidator(WorldValidator):
    """回答を加えた確認で、最初の`failures`回だけ下限の不足でない必須条件エラーを返す。"""

    failures: int = 1
    trial_calls: int = 0

    def validate(self, plan, source_members, specification):  # type: ignore[no-untyped-def]
        if specification.late_starts:
            self.trial_calls += 1
            if self.trial_calls <= self.failures:
                issue = ValidationIssue(ValidationCode.CAPACITY, "上限NG", 5)
                return ValidationReport((issue,), (), (), (), ())
        return super().validate(plan, source_members, specification)


def _world_resolving_seventh() -> World:
    return World(base=frozenset({(7, H21)}), resolves={10: frozenset({(7, H21)})})


def test_timeout_while_checking_answer_is_timeout_not_note() -> None:
    """回答を確かめる最適化の時間切れは、注記に変えず時間切れのエラーとして伝える（ADR 0035）。"""

    optimizer = TimeoutOnTrialOptimizer(_world_resolving_seventh())
    build = BuildTeamPlan(rules=RULES, optimizer=optimizer, validator=WorldValidator())

    with pytest.raises(SearchTimeoutError):
        build.execute(MEMBERS, SPECIFICATION, [answer((7, H21), 10)])


def test_checking_answer_retries_after_invalid_candidate() -> None:
    """回答を確かめる最適化も、下限の不足でない必須条件エラーの候補は同じ指定で再試行する。"""

    optimizer = WorldOptimizer(_world_resolving_seventh())
    validator = FlakyTrialValidator(failures=1)
    build = BuildTeamPlan(rules=RULES, optimizer=optimizer, validator=validator)

    result = build.execute(MEMBERS, SPECIFICATION, [answer((7, H21), 10)])

    assert isinstance(result, ValidatedTeamPlan)
    assert result.notes == ()
    assert optimizer.calls == [
        (frozenset(), None),
        (frozenset({10}), frozenset()),
        (frozenset({10}), frozenset()),
    ]


def test_checking_answer_stops_with_build_error_after_retry_limit() -> None:
    """回答を確かめる最適化で再試行の上限に達したら、注記に変えずBuildError（終了コード2）にする。"""

    optimizer = WorldOptimizer(_world_resolving_seventh())
    validator = FlakyTrialValidator(failures=RULES.maximum_validation_attempts)
    build = BuildTeamPlan(rules=RULES, optimizer=optimizer, validator=validator)

    with pytest.raises(BuildError, match="再配置後も検証NG"):
        build.execute(MEMBERS, SPECIFICATION, [answer((7, H21), 10)])


def test_grouped_question_accepts_answer_for_time_it_fixes() -> None:
    """まとめた問いでは、書いた時刻の休止がなくなる回答だけを受け入れ、残りの時刻を問い直す。"""

    world = World(
        base=frozenset({(7, H21), (7, H2130)}),
        resolves={10: frozenset({(7, H2130)})},
    )

    first_time = run(world, [answer((7, H21), 10)])
    second_time = run(world, [answer((7, H2130), 10)])

    assert _questions(first_time) == [(1, 7, (H21, H2130), True)]
    assert "受け入れませんでした" in first_time.notes[0]
    assert _questions(second_time) == [(1, 7, (H21,), True)]
    assert second_time.notes == ()


def test_rejected_answer_whose_target_is_fixed_later_is_noted_as_unused() -> None:
    """受け入れなかった回答も、後の回答で対象が直れば最後の編成で使わなかったと注記する（FRM-090の性質(6)）。"""

    world = World(
        base=frozenset({(7, H21), (8, H21)}),
        resolves={10: frozenset({(7, H21), (8, H21)})},
        creates={9: frozenset({(5, H21)})},
    )

    result = run(world, [answer((7, H21), 9), answer((8, H21), 10)])

    assert isinstance(result, ValidatedTeamPlan)
    assert len(result.notes) == 1
    assert "第7隊 21:00への回答" in result.notes[0]
    assert "使いませんでした" in result.notes[0]


def test_same_specification_that_did_not_fix_target_is_noted_as_such() -> None:
    """受け入れた指定と同じ指定で対象が直らない回答は、別の指定と取り違えずに注記する。"""

    world = World(
        base=frozenset({(7, H21), (8, H21)}),
        resolves={10: frozenset({(7, H21)})},
    )

    result = run(world, [answer((7, H21), 10), answer((8, H21), 10)])

    assert _questions(result) == [(1, 8, (H21,), True)]
    assert "第8隊 21:00への回答" in result.notes[0]
    assert "先に受け入れた同じ指定では対象の休止が直らなかった" in result.notes[0]
    assert "別の指定" not in result.notes[0]


@dataclass
class IgnoringAllowedOptimizer(WorldOptimizer):
    """休止を許した組を無視して編成を返す、誤ったOptimizer。"""

    def optimize(self, members, specification, allowed_shortfalls=None):  # type: ignore[no-untyped-def]
        return super().optimize(members, specification, None)


def test_optimizer_ignoring_allowed_shortfalls_is_build_error() -> None:
    """許した組の外に休止のある編成を返すOptimizerの誤りは、受け入れずにBuildErrorにする。"""

    world = World(
        base=frozenset({(7, H21)}),
        resolves={10: frozenset({(7, H21)})},
        creates={10: frozenset({(5, H21)})},
    )
    optimizer = IgnoringAllowedOptimizer(world)
    build = BuildTeamPlan(rules=RULES, optimizer=optimizer, validator=WorldValidator())

    with pytest.raises(BuildError, match="休止を許した"):
        build.execute(MEMBERS, SPECIFICATION, [answer((7, H21), 10)])
