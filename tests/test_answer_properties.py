"""FRM-090の回答を受けた実行の性質のテストの枠（作成者の仮定A-10、A-41、ADR 0035）。

分割案の2で枠を作り、分割案の3と4で選択肢（隊数を減らす、明示して許す、遅れて出撃させる案の列挙）を
加えるときに性質のテストを足す。ここでは架空の世界（`answer_world`）を生成し、示した問いの対象だけに
答えた回答について、次を確かめる。

- (1) 入力のエラーにならない
- (2) 出力するか、まだ決まらない（隊、時間帯）だけについて問いを示し直す。新しく不足を生まない
- (4) 回答を1つでも受け入れれば、決まらない（隊、時間帯）が減る
- (5) 回答の中の指定の順によらず、同じ問い合わせか同じ出力になる
- (6) 判定に使う編成で最適性を示せなければ、時間切れのエラーになる
"""

from random import Random

from hypothesis import example, given
from hypothesis import strategies as st

from answer_world import (
    H21,
    H22,
    H23,
    H2130,
    LATE_TEAMS,
    MEMBERS,
    SPECIFICATION,
    World,
    answer,
    run,
    use_case,
)
from kvk_team.team_building.application.build_team_plan import (
    LowerBoundShortfallError,
)
from kvk_team.team_building.application.ports import SearchTimeoutError
from kvk_team.team_building.domain.answers import Answer
from kvk_team.team_building.domain.specification import SpecificationError
from kvk_team.team_building.domain.validation import ValidatedTeamPlan

KEYS = tuple((team, start) for team in range(4, 11) for start in (H21, H2130, H22, H23))
STARTS = (H22, H22 + 30, H23)


@st.composite
def worlds(
    draw: st.DrawFn,
    optimal: bool = True,
    optimal_with_answers: bool = True,
    unproven: bool = False,
) -> World:
    """遅らせる隊ごとに直す不足と生む不足、同時に遅らせられない組を持つ世界を作る。"""

    base = draw(st.frozensets(st.sampled_from(KEYS), min_size=1, max_size=6))
    resolves = {
        team: draw(st.frozensets(st.sampled_from(sorted(base)), max_size=3))
        for team in LATE_TEAMS
    }
    creates = {
        team: draw(st.frozensets(st.sampled_from(KEYS), max_size=1))
        for team in LATE_TEAMS
    }
    conflicts = draw(
        st.frozensets(
            st.frozensets(st.sampled_from(LATE_TEAMS), min_size=2, max_size=2),
            max_size=3,
        )
    )
    return World(
        base=base,
        resolves=resolves,
        creates=creates,
        conflicts=conflicts,
        optimal_without_answers=optimal,
        optimal_with_answers=optimal_with_answers,
        unproven=draw(
            st.frozensets(
                st.frozensets(st.sampled_from(LATE_TEAMS), min_size=1, max_size=2),
                max_size=3,
            )
        )
        if unproven
        else frozenset(),
    )


def _shown_targets(world: World) -> list[tuple[int, int]]:
    """回答なしの実行で、回答を書けると示した（序盤の）問いの（隊、時間帯）を返す。

    序盤以外の問いには、この版では回答できないと示すため含めない（利用者の決定、2026-11-10）。
    """

    result = run(world, [])
    assert isinstance(result, LowerBoundShortfallError), result
    return [
        (question.team_number, slot.start_minutes)
        for question in result.questions
        if question.answerable
        for slot in question.time_slots
    ]


@st.composite
def answered_worlds(
    draw: st.DrawFn, optimal_with_answers: bool = True, unproven: bool = False
) -> tuple[World, list[Answer]]:
    """世界と、示した問いの対象だけに答えた回答を作る。"""

    world = draw(worlds(optimal_with_answers=optimal_with_answers, unproven=unproven))
    targets = _shown_targets(world)
    if not targets:
        return world, []
    answers = draw(
        st.lists(
            st.builds(
                answer,
                st.sampled_from(targets),
                st.sampled_from(LATE_TEAMS),
                st.sampled_from(STARTS),
            ),
            max_size=4,
        )
    )
    return world, answers


ACCEPTING_CASE = (
    World(
        base=frozenset({(7, H21), (8, H21)}),
        resolves={9: frozenset({(7, H21)})},
    ),
    [answer((7, H21), 9)],
)
"""回答を必ず受け入れる例。生成した例で受け入れが起きなくても、性質(4)を素通りさせない。"""


def _remaining(result: object) -> frozenset[tuple[int, int]]:
    if isinstance(result, ValidatedTeamPlan):
        return frozenset()
    assert isinstance(result, LowerBoundShortfallError), result
    return frozenset(
        (question.team_number, slot.start_minutes)
        for question in result.questions
        for slot in question.time_slots
    )


def _signature(result: object) -> tuple[object, ...]:
    if isinstance(result, ValidatedTeamPlan):
        return ("output", result.plan, result.notes)
    assert isinstance(result, LowerBoundShortfallError), result
    return ("questions", str(result), result.questions, result.notes)


@given(answered_worlds())
def test_answers_to_shown_targets_are_not_input_errors(
    case: tuple[World, list[Answer]],
) -> None:
    """性質(1)(2): 示した問いの対象だけに答えた回答は、出力か問いの示し直しになる。"""

    world, answers = case

    result = run(world, answers)

    assert not isinstance(result, SpecificationError)
    assert isinstance(result, (ValidatedTeamPlan, LowerBoundShortfallError)), result
    # 新しく不足を生まず、問いは回答なしの問いの対象の中に限る。
    assert _remaining(result) <= _remaining(run(world, []))


@example(ACCEPTING_CASE)
@given(answered_worlds())
def test_accepting_an_answer_reduces_undetermined_targets(
    case: tuple[World, list[Answer]],
) -> None:
    """性質(4): 回答を1つでも受け入れれば、決まらない（隊、時間帯）が減る。"""

    world, answers = case

    before = _remaining(run(world, []))
    result = run(world, answers)
    after = _remaining(result)

    accepted_any = len(result.notes) < len(set(answers)) if answers else False
    if accepted_any:
        assert after < before
    if (world, answers) == ACCEPTING_CASE:
        assert accepted_any


@given(answered_worlds(), st.randoms(use_true_random=False))
def test_result_does_not_depend_on_answer_order(
    case: tuple[World, list[Answer]], random: Random
) -> None:
    """性質(5): 回答の中の指定の順によらず、同じ問い合わせか同じ出力になる。"""

    world, answers = case
    shuffled = list(answers)
    random.shuffle(shuffled)

    assert _signature(run(world, answers)) == _signature(run(world, shuffled))


@given(worlds(optimal=False), st.lists(st.sampled_from(LATE_TEAMS), max_size=2))
def test_unproven_judgment_plan_is_timeout(world: World, teams: list[int]) -> None:
    """性質(6): 判定に使う編成で最適性を示せなければ、回答によらず時間切れのエラーになる。"""

    opening = [key for key in sorted(world.base) if key[1] in (H21, H2130)]
    answers = [answer(opening[0], team) for team in teams] if opening else []

    assert isinstance(run(world, answers), SearchTimeoutError)


UNPROVEN_TRIAL_CASE = (
    World(
        base=frozenset({(7, H21), (8, H21)}),
        resolves={9: frozenset({(7, H21)}), 10: frozenset({(8, H21)})},
        unproven=frozenset({frozenset({9})}),
    ),
    [answer((7, H21), 9), answer((8, H21), 10)],
)
"""不足が残り最適性を示せない確認の後に、最適性を示せる確認が続く例。"""


@example(UNPROVEN_TRIAL_CASE)
@given(answered_worlds(unproven=True))
def test_unproven_trial_with_remaining_shortfall_is_timeout(
    case: tuple[World, list[Answer]],
) -> None:
    """性質(6): 回答を確かめた編成に不足が残り、最適性を示せなければ時間切れのエラーになる。

    見つかった編成の不足が0なら、最適性を示せなくても受け入れる（最後の出力はFRM-049に従う）。
    """

    world, answers = case
    build, optimizer = use_case(world)

    try:
        result: object = build.execute(MEMBERS, SPECIFICATION, answers)
    except Exception as error:  # noqa: BLE001 - 結果として比べるため例外も値にする
        result = error

    unproven_with_shortfall = any(
        allowed is not None and keys and not optimal
        for allowed, keys, optimal in optimizer.solved
    )
    if unproven_with_shortfall:
        assert isinstance(result, SearchTimeoutError), result
    else:
        assert isinstance(result, (ValidatedTeamPlan, LowerBoundShortfallError)), result
