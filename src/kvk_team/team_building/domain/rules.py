"""KvKチーム編成ルールの信頼できる唯一の定義元。"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from kvk_team.team_building.domain.member import Tier
from kvk_team.team_building.domain.plan import TimeSlot, time_slots
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
class KvKRules:
    """1回のKvK編成に使用する不変の制約と評価値。"""

    team_master: TeamMaster
    """運用設定から読み込んだチームマスタ。読み込みはアダプターとインターフェースで行う。"""
    tier_power: Mapping[Tier, int] = field(
        default_factory=lambda: DEFAULT_TIER_POWER,
        init=False,
    )
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
    def time_slots(self) -> tuple[TimeSlot, ...]:
        """戦闘時間を等分した時間帯を返す。"""

        event = self.team_master.event_time
        return time_slots(event.start_minutes, event.end_minutes)

    @property
    def member_cap(self) -> int:
        """第4隊以降の出撃人数の上限を返す。"""

        return self.team_master.member_cap
