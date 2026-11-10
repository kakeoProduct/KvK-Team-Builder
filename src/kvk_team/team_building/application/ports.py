"""KvKチーム編成のユースケースが外部の実装へ求める境界。"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.plan import TeamPlan
from kvk_team.team_building.domain.specification import OperatorSpecification
from kvk_team.team_building.domain.team_master import TeamMaster
from kvk_team.team_building.domain.validation import ValidationReport


@dataclass(frozen=True, slots=True)
class SolvedPlan:
    """Optimizerが編成を見つけた結果。

    `proven_optimal`は探索の制限内に最適だと示せたかを表す。示せなかった編成は、
    下限の不足の判定に使えず（FRM-090の性質(6)）、出力にはFRM-049の警告を付ける（Issue 3）。
    """

    plan: TeamPlan
    proven_optimal: bool


@dataclass(frozen=True, slots=True)
class ProvenInfeasible:
    """必須条件を満たす編成がないことをOptimizerが証明した結果。"""

    reason: str


OptimizationOutcome = SolvedPlan | ProvenInfeasible
"""Optimizerの結果。時間切れは結果にせず、時間切れのエラーとして送出する（ADR 0019）。"""


class TeamPlanOptimizerPort(Protocol):
    """所属固定の編成を生成する境界。"""

    def optimize(
        self,
        members: Sequence[Member],
        specification: OperatorSpecification,
    ) -> OptimizationOutcome:
        """編成の候補を生成する。"""


class TeamPlanValidatorPort(Protocol):
    """所属固定の編成を事後検証する境界。"""

    def validate(
        self,
        plan: TeamPlan,
        source_members: Sequence[Member],
        specification: OperatorSpecification,
    ) -> ValidationReport:
        """編成の候補を検証する。"""


class TeamMasterRepository(Protocol):
    """永続化方式からチームマスタを取得する境界。"""

    def load(self) -> TeamMaster:
        """チームマスタを読み込む。"""


class OperatorSpecificationRepository(Protocol):
    """永続化方式から運用者の指定を取得する境界。"""

    def load(self) -> OperatorSpecification:
        """運用者の指定を読み込む。"""
