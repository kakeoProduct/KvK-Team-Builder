"""参加者から検証済みの時間帯別編成を作るユースケース。"""

from collections.abc import Sequence
from dataclasses import dataclass

from kvk_team.team_building.application.ports import (
    DynamicOptimizerPort,
    DynamicValidatorPort,
)
from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.validation import (
    DynamicValidationReport,
    ValidatedTeamPlan,
)


class BuildError(RuntimeError):
    """すべての動的編成候補が事後検証に失敗した場合に送出する。"""


@dataclass(frozen=True, slots=True)
class BuildTeamPlan:
    """最適化と独立検証を繰り返し、必須条件を満たす編成だけを返す。

    入力形式と出力形式を扱わない。参加者はドメイン型で受け取り、結果は`ValidatedTeamPlan`で返す。
    """

    rules: KvKRules
    optimizer: DynamicOptimizerPort
    validator: DynamicValidatorPort

    def execute(self, members: Sequence[Member]) -> ValidatedTeamPlan:
        """Validatorが必須条件OKを返した編成を、検証済み編成として返す。"""

        source_members = list(members)
        last_report: DynamicValidationReport | None = None
        for _ in range(self.rules.maximum_validation_attempts):
            plan = self.optimizer.optimize(source_members)
            last_report = self.validator.validate(plan, source_members)
            if last_report.is_valid:
                return ValidatedTeamPlan(plan=plan, report=last_report)

        issue_text = (
            "; ".join(issue.message for issue in last_report.issues)
            if last_report
            else "検証結果がありません"
        )
        raise BuildError(
            f"{self.rules.maximum_validation_attempts}回の再配置後も検証NGです: "
            f"{issue_text}"
        )
