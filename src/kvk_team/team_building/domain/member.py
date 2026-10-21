"""参加者のドメインモデル。"""

from dataclasses import dataclass
from enum import Enum, IntEnum

MINUTES_PER_HOUR = 60
KVK_START_HOUR = 21
KVK_START_MINUTES = KVK_START_HOUR * MINUTES_PER_HOUR


class Tier(str, Enum):
    """対応する参加者Tier。"""

    G8 = "G8"
    G7 = "G7"
    G6 = "G6"
    G5 = "G5"
    OTHER = "OTHER"

    @classmethod
    def from_heading(cls, value: str) -> "Tier":
        """Markdown見出しが表すTierを返す。"""

        normalized = value.strip().upper()
        return cls(normalized) if normalized in cls._value2member_map_ else cls.OTHER


class Availability(IntEnum):
    """参加価値が低い順に並べた参加可能時間の優先度。"""

    LATE_JOIN = 1
    UNTIL_23 = 2
    UNTIL_24 = 3
    UNTIL_25 = 4
    UNTIL_END = 5


@dataclass(frozen=True, slots=True)
class Member:
    """入力Markdownから解析した1人のKvK参加者。"""

    name: str
    alliance: str
    tier: Tier
    has_vc: bool = False
    starts_at_21: bool = True
    availability: Availability = Availability.UNTIL_END
    special_unit: bool = False
    start_time_minutes: int | None = KVK_START_MINUTES
    end_time_minutes: int | None = None

    def __post_init__(self) -> None:
        """最適化前に識別情報が不完全な参加者を拒否する。"""

        if not self.name.strip():
            raise ValueError("member name must not be empty")
        if not self.alliance.strip():
            raise ValueError("alliance name must not be empty")
        if not self.starts_at_21 and self.start_time_minutes == KVK_START_MINUTES:
            object.__setattr__(self, "start_time_minutes", None)
        if (
            self.start_time_minutes is not None
            and self.end_time_minutes is not None
            and self.end_time_minutes <= self.start_time_minutes
        ):
            raise ValueError("participation end time must be after start time")
