"""参加者と運用者の指定から、検証済みの所属固定の編成を作るユースケース。"""

from collections.abc import Sequence
from dataclasses import dataclass

from kvk_team.team_building.application.ports import (
    ProvenInfeasible,
    TeamPlanOptimizerPort,
    TeamPlanValidatorPort,
)
from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.specification import (
    OperatorSpecification,
    resolve_leaders,
)
from kvk_team.team_building.domain.team import team_name
from kvk_team.team_building.domain.validation import (
    ValidatedTeamPlan,
    ValidationIssue,
    ValidationReport,
    format_clock,
)


class BuildError(RuntimeError):
    """必須条件を満たす編成を出力できない場合に送出する。"""


class NoValidPlanError(BuildError):
    """必須条件を満たす編成がないとOptimizerが証明した場合に送出する。"""


class LowerBoundShortfallError(BuildError):
    """延長境界時刻より前の休止が避けられないと示せた場合に送出する（FRM-048）。

    6人以下の禁止（FRM-039）と序盤の8人（FRM-040）は分割案の3と4で加える。

    選択肢（遅れて出撃させる、隊数を減らす、明示して許す）はIssue 3と4で加える。
    それまでは選択肢を示さず、理由だけを示して出力を止める。
    """

    def __init__(self, shortfalls: Sequence[ValidationIssue]) -> None:
        self.shortfalls = tuple(shortfalls)
        lines = "\n".join(f"- {_describe(issue)}" for issue in self.shortfalls)
        super().__init__(
            "延長境界時刻より前に休止になる隊があるため、編成を出力しません。"
            "参加者一覧かリーダー一覧を見直してください。\n" + lines
        )


class ShortfallUndeterminedError(BuildError):
    """下限の不足が避けられないかを、探索の制限内に確定できなかった場合に送出する。

    最適だと示せない編成で下限の不足を判定すると、避けられる不足を運用者へ問うことになる。
    このため時間切れのエラーとして扱う（FRM-090の性質(6)、ADR 0019）。
    """


def _describe(issue: ValidationIssue) -> str:
    """検証結果へ隊と時刻を付ける。"""

    parts = []
    if issue.time_slot is not None:
        parts.append(format_clock(issue.time_slot.start_minutes))
    if (
        issue.team_number is not None
        and team_name(issue.team_number) not in issue.message
    ):
        parts.append(team_name(issue.team_number))
    prefix = " ".join(parts)
    return f"{prefix}: {issue.message}" if prefix else issue.message


@dataclass(frozen=True, slots=True)
class BuildTeamPlan:
    """最適化と独立検証を繰り返し、必須条件を満たす編成だけを返す。

    入力形式と出力形式を扱わない。参加者と運用者の指定はドメイン型で受け取り、
    結果は`ValidatedTeamPlan`で返す。
    """

    rules: KvKRules
    optimizer: TeamPlanOptimizerPort
    validator: TeamPlanValidatorPort

    def execute(
        self,
        members: Sequence[Member],
        specification: OperatorSpecification,
    ) -> ValidatedTeamPlan:
        """Validatorが必須条件OKを返した編成を、検証済み編成として返す。

        リーダーが参加者一覧で1人に決まらない場合は、最適化の前に`SpecificationError`を送出する。
        """

        source_members = list(members)
        resolve_leaders(specification, source_members)
        last_report: ValidationReport | None = None
        for _ in range(self.rules.maximum_validation_attempts):
            outcome = self.optimizer.optimize(source_members, specification)
            if isinstance(outcome, ProvenInfeasible):
                raise NoValidPlanError(outcome.reason)
            last_report = self.validator.validate(
                outcome.plan, source_members, specification
            )
            if last_report.is_valid:
                return ValidatedTeamPlan(
                    plan=outcome.plan,
                    report=last_report,
                    proven_optimal=outcome.proven_optimal,
                )
            if last_report.has_only_shortfalls:
                if not outcome.proven_optimal:
                    raise ShortfallUndeterminedError(
                        "探索の制限内に最適な編成を示せなかったため、休止が避けられないかを"
                        "確定できません。時間切れのため、負荷の低い環境で再実行するか、"
                        "制限時間を延ばしてください"
                    )
                raise LowerBoundShortfallError(last_report.shortfalls)

        issue_text = (
            "; ".join(issue.message for issue in last_report.issues)
            if last_report
            else "検証結果がありません"
        )
        raise BuildError(
            f"{self.rules.maximum_validation_attempts}回の再配置後も検証NGです: "
            f"{issue_text}"
        )
