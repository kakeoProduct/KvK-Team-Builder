"""KvKチーム編成ルールの信頼できる唯一の定義元。"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from kvk_team.team_building.domain.member import Tier
from kvk_team.team_building.domain.team import TeamLabel
from kvk_team.team_building.domain.team_master import TeamMaster

DEFAULT_TIER_POWER: Mapping[Tier, int] = MappingProxyType(
    {
        Tier.G8: 400,
        Tier.G7: 300,
        Tier.G6: 200,
        Tier.G5: 100,
        Tier.OTHER: 20,
    }
)


@dataclass(frozen=True, slots=True)
class ObjectiveWeights:
    """CP-SAT最適化目的に使用する相対的な重み。"""

    priority_power: int = 100
    underfilled_team: int = 100_000
    member_team_change: int = 1_000
    ninth_member: int = 100


@dataclass(frozen=True, slots=True)
class KvKRules:
    """1回のKvK編成に使用する不変の制約と評価値。"""

    team_master: TeamMaster
    """運用設定から読み込んだチームマスタ。読み込みはアダプターとインターフェースで行う。"""
    tier_power: Mapping[Tier, int] = field(
        default_factory=lambda: DEFAULT_TIER_POWER,
        init=False,
    )
    objective_weights: ObjectiveWeights = field(default_factory=ObjectiveWeights)
    maximum_optimization_seconds: float = 30.0
    maximum_deterministic_time: float | None = None
    """CP-SATの決定的時間による探索上限。指定時は実行環境の速さに依存せず打ち切る。"""
    solver_worker_count: int = 8
    solver_random_seed: int = 42
    maximum_validation_attempts: int = 3

    def __post_init__(self) -> None:
        """有効なチームを表現できないルールの組み合わせを拒否する。"""

        if self.maximum_optimization_seconds <= 0:
            raise ValueError("optimization time limit must be positive")
        if (
            self.maximum_deterministic_time is not None
            and self.maximum_deterministic_time <= 0
        ):
            raise ValueError("deterministic time limit must be positive")
        if self.solver_worker_count < 1:
            raise ValueError("solver worker count must be positive")
        if self.maximum_validation_attempts < 1:
            raise ValueError("validation attempt count must be positive")

    @property
    def team_labels(self) -> tuple[TeamLabel, ...]:
        """すべての固定チームラベルを優先順で返す。"""

        return self.team_master.team_labels

    @property
    def rally_leaders(self) -> Mapping[TeamLabel, str]:
        """JSONチームマスタで定義した固定集結主を返す。"""

        return self.team_master.rally_leaders

    @property
    def vc_required_teams(self) -> tuple[TeamLabel, ...]:
        """JSONチームマスタでVC必須としたチームを返す。"""

        return self.team_master.vc_required_teams
