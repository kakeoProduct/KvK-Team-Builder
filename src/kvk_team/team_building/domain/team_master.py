"""永続化方式に依存しないチームマスタのドメインモデル。

チームマスタはRepositoryで管理する常設の既定値（戦闘時間、出撃人数の上限）だけを持つ。
リーダー一覧などの個人名を含む運用者の指定は、イベントのフォルダの`settings.json`から
読む（DAT-007、ADR 0029、ADR 0034）。
"""

from dataclasses import dataclass

from kvk_team.team_building.domain.member import MINUTES_PER_HOUR
from kvk_team.team_building.domain.team import SLOT_MINUTES, SORTIE_FLOOR

TEAM_MASTER_SCHEMA_VERSION = 2
"""所属固定のモデルのチームマスタの版。1は隊ごとの集結主を持つ以前の形。"""


@dataclass(frozen=True, slots=True)
class EventTimeSettings:
    """時間帯別編成に使用するイベント時間設定。時間帯の長さは固定値の30分とする（ADR 0034）。"""

    start_minutes: int
    end_minutes: int

    def __post_init__(self) -> None:
        """30分の区切りに乗らない戦闘時間を拒否する。

        開始が区切りに乗らないと、時間帯が延長境界時刻（24:00）をまたぎ、境界より前か後かが決まらない。
        """

        duration = self.end_minutes - self.start_minutes
        if duration <= 0:
            raise ValueError("イベント終了時刻は開始時刻より後にしてください")
        if self.start_minutes % SLOT_MINUTES:
            raise ValueError(
                f"戦闘開始は{SLOT_MINUTES}分の区切り（例: 21:00、21:30）にしてください"
            )
        if duration % SLOT_MINUTES:
            raise ValueError(
                f"戦闘時間は{SLOT_MINUTES}分の時間帯へ等分できる長さにしてください"
            )

    @property
    def slot_minutes(self) -> int:
        """時間帯の長さ（分）を返す。"""

        return SLOT_MINUTES

    @property
    def slot_starts(self) -> tuple[int, ...]:
        """各時間スロットの開始時刻を返す。

        本体のコードは`KvKRules.time_slots`を使う。テストの生成戦略は、本体と別に時間帯を数えるため
        こちらを使う。
        """

        return tuple(range(self.start_minutes, self.end_minutes, self.slot_minutes))


@dataclass(frozen=True, slots=True)
class TeamMaster:
    """常設の既定値。"""

    schema_version: int
    event_time: EventTimeSettings
    member_cap: int
    """第4隊以降の出撃人数の上限（FRM-030の全隊共通の値）。"""

    def __post_init__(self) -> None:
        """この版で扱えない値を拒否する。"""

        if self.schema_version != TEAM_MASTER_SCHEMA_VERSION:
            raise ValueError(
                f"schema_versionは{TEAM_MASTER_SCHEMA_VERSION}にしてください"
            )
        if self.member_cap < SORTIE_FLOOR:
            raise ValueError(
                f"出撃人数の上限は下限の{SORTIE_FLOOR}人以上にしてください"
            )


def parse_clock(value: str) -> int:
    """`HH:MM`形式を日跨ぎ対応の分へ変換する。"""

    hour_text, minute_text = value.split(":", maxsplit=1)
    hour = int(hour_text)
    minute = int(minute_text)
    if hour < 0 or minute < 0 or minute >= MINUTES_PER_HOUR:
        raise ValueError(f"不正な時刻です: {value}")
    return hour * MINUTES_PER_HOUR + minute
