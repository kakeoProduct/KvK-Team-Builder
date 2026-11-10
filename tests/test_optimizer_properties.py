"""生成した参加者で、Optimizerの出力が必須条件を満たすことを検証する性質テスト。"""

from hypothesis import given, settings

from deterministic_solver import deterministic_rules
from kvk_team.team_building.adapters.optimization.cp_sat_team_optimizer import (
    MembershipOptimizer,
)
from kvk_team.team_building.application.ports import SolvedPlan
from kvk_team.team_building.domain.validation import TeamPlanValidator
from team_plan_strategies import Scenario, scenarios

OPTIMIZER_EXAMPLES = 5
"""CP-SATは1件で数秒かかることがあるため、品質ゲートの実行時間を抑える件数に絞る。"""


@settings(max_examples=OPTIMIZER_EXAMPLES)
@given(scenarios())
def test_optimizer_output_passes_independent_validator(scenario: Scenario) -> None:
    """有効な編成が存在する参加者から、独立Validatorが受理する編成を作る。

    Validatorは別枠を入力から計算し直すため、Optimizerが開始時刻の未定な参加者を
    別枠へ分けたことは、編成結果から直接確かめる。
    """

    rules = deterministic_rules()
    members = scenario.source_members

    outcome = MembershipOptimizer(rules).optimize(members, scenario.specification)

    assert isinstance(outcome, SolvedPlan)
    report = TeamPlanValidator(rules).validate(
        outcome.plan, members, scenario.specification
    )
    assert report.issues == ()
    assert set(outcome.plan.undecided) == set(scenario.undecided)
