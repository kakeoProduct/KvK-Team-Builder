"""KvKチーム編成のユースケースが外部の実装へ求める境界。"""

from typing import Protocol

from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.schedule import DynamicTeamPlan
from kvk_team.team_building.domain.team_master import TeamMaster
from kvk_team.team_building.domain.validation import DynamicValidationReport


class DynamicOptimizerPort(Protocol):
    """時間帯別編成を生成する境界。"""

    def optimize(self, members: list[Member]) -> DynamicTeamPlan:
        """動的編成候補を生成する。"""


class DynamicValidatorPort(Protocol):
    """時間帯別編成を事後検証する境界。"""

    def validate(
        self,
        plan: DynamicTeamPlan,
        source_members: list[Member],
    ) -> DynamicValidationReport:
        """動的編成候補を検証する。"""


class TeamMasterRepository(Protocol):
    """永続化方式からチームマスタを取得する境界。"""

    def load(self) -> TeamMaster:
        """チームマスタを読み込む。"""
