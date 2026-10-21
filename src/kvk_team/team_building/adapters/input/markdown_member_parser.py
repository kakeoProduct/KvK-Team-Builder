"""実運用の参加者Markdownをドメインオブジェクトへ解析する。"""

import re
import unicodedata
from dataclasses import dataclass
from typing import TypeVar

from kvk_team.team_building.domain.member import (
    KVK_START_MINUTES,
    MINUTES_PER_HOUR,
    Availability,
    Member,
    Tier,
)

ContextValue = TypeVar("ContextValue")

ALLIANCE_PATTERN = re.compile(r"^(?:同盟名|同盟)\s*[:：]\s*(?P<name>.+?)\s*$")
TIER_PATTERN = re.compile(
    r"^(?:#{1,6}\s*)?"
    r"(?P<tier>G\d+(?:以下)?|その他)\s*[:：]?\s*(?P<members>.*)$",
    re.IGNORECASE,
)
BULLET_PATTERN = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)")
LEGEND_PATTERN = re.compile(r"^[◯○〇△◇]\s*[:：]")
IGNORED_LINE_PATTERN = re.compile(
    r"^(?:チーム名\s*[:：]?|[（(]参加出来る時間記入[）)])$"
)
START_SECTION_PATTERN = re.compile(
    r"^(?:[^()（）]+[（(])?最初から参加(?:できる)?[）)]?$"
)
LATE_SECTION_PATTERN = re.compile(r"^(?:[^()（）]+[（(])?途中(?:から)?参加[）)]?$")
MEMBER_SEPARATOR_PATTERN = re.compile(r"[、,､]+")
JOINED_MEMBER_PATTERN = re.compile(r"(?<=[)）])(?=[^\s、,､◇△◯○〇])")

VC_PATTERN = re.compile(r"(?:◇|\[VC\])", re.IGNORECASE)
MONTHLY_PATTERN = re.compile(r"[◯○〇]")
EARLY_LEAVE_PATTERN = re.compile(r"△")
EXPLICIT_START_PATTERN = re.compile(r"\[21:00\]", re.IGNORECASE)
SPECIAL_UNIT_PATTERN = re.compile(r"(?:\[特殊部隊\]|特殊部隊)")
LATE_JOIN_PATTERN = re.compile(r"(?:\[途中参加\]|途中参加)")
LATE_TIME_PATTERN = re.compile(
    r"(?:21時?半|22時?|23時?)(?:半|頃|前後)?(?:頃)?\s*"
    r"(?:[-~〜～]|から)"
)
PARENTHETICAL_PATTERN = re.compile(r"[\[(（][^\])）]*[\])）]")
STANDALONE_TIME_PATTERN = re.compile(
    r"(?:[〜～~]?\d{1,2}時(?:半)?(?:頃)?|[〜～~]?\d{4}頃?)"
)
LAST_UNTIL_PATTERN = re.compile(r"(?:最後まで|ラスト)")
CLOCK_PATTERN = re.compile(
    r"(?P<compact>2[1-5][0-5]\d)|"
    r"(?P<hour>2[1-5])(?:時)?(?P<half>半)?"
)
UNTIL_23_MINUTES = 23 * MINUTES_PER_HOUR
UNTIL_24_MINUTES = 24 * MINUTES_PER_HOUR
UNTIL_25_MINUTES = 25 * MINUTES_PER_HOUR


class ParseError(ValueError):
    """参加者Markdownが曖昧または不完全な場合に送出する。"""


@dataclass(slots=True)
class MarkdownMemberParser:
    """同盟、参加区分、Tier、メンバーメタデータを解析する。"""

    def parse(self, markdown: str) -> list[Member]:
        """Markdownテキストを解析し、入力順でメンバーを返す。"""

        members: list[Member] = []
        current_alliance: str | None = None
        current_tier: Tier | None = None
        section_starts_at_21 = True
        section_pending_for_alliance = False
        seen_names: set[str] = set()

        for line_number, source_line in enumerate(markdown.splitlines(), start=1):
            line = unicodedata.normalize("NFKC", source_line).strip()
            if not line or line.startswith("<!--"):
                continue
            if LEGEND_PATTERN.match(line) or IGNORED_LINE_PATTERN.fullmatch(line):
                continue

            if START_SECTION_PATTERN.fullmatch(line):
                section_starts_at_21 = True
                section_pending_for_alliance = True
                continue
            if LATE_SECTION_PATTERN.fullmatch(line):
                section_starts_at_21 = False
                section_pending_for_alliance = True
                continue

            alliance_match = ALLIANCE_PATTERN.fullmatch(line)
            if alliance_match:
                if not section_pending_for_alliance:
                    section_starts_at_21 = True
                current_alliance = alliance_match.group("name").strip()
                current_tier = None
                section_pending_for_alliance = False
                continue

            tier_match = TIER_PATTERN.fullmatch(line)
            if tier_match:
                current_alliance = self._require_context(
                    current_alliance, line_number, "同盟名"
                )
                section_pending_for_alliance = False
                current_tier = Tier.from_heading(tier_match.group("tier"))
                inline_members = tier_match.group("members").strip()
                if inline_members:
                    self._append_members(
                        source=inline_members,
                        alliance=current_alliance,
                        tier=current_tier,
                        starts_at_21=section_starts_at_21,
                        line_number=line_number,
                        members=members,
                        seen_names=seen_names,
                    )
                continue

            if line.startswith("#"):
                continue

            current_alliance = self._require_context(
                current_alliance, line_number, "同盟名"
            )
            current_tier = self._require_context(current_tier, line_number, "Tier")
            section_pending_for_alliance = False
            self._append_members(
                source=BULLET_PATTERN.sub("", line),
                alliance=current_alliance,
                tier=current_tier,
                starts_at_21=section_starts_at_21,
                line_number=line_number,
                members=members,
                seen_names=seen_names,
            )

        if not members:
            raise ParseError("参加者が見つかりません")
        return members

    def _append_members(
        self,
        source: str,
        alliance: str,
        tier: Tier,
        starts_at_21: bool,
        line_number: int,
        members: list[Member],
        seen_names: set[str],
    ) -> None:
        """入力の1行を分割し、検証済みメンバーを追加する。"""

        for member_source in self._split_members(source):
            member = self._parse_member(
                line=member_source,
                alliance=alliance,
                tier=tier,
                section_starts_at_21=starts_at_21,
                line_number=line_number,
            )
            if member.name in seen_names:
                raise ParseError(
                    f"line {line_number}: 参加者名が重複しています: {member.name}"
                )
            seen_names.add(member.name)
            members.append(member)

    @staticmethod
    def _split_members(source: str) -> list[str]:
        """時間注記の直後に連結された項目を含め、カンマ区切りを分割する。"""

        members: list[str] = []
        for comma_part in MEMBER_SEPARATOR_PATTERN.split(source):
            for joined_part in JOINED_MEMBER_PATTERN.split(comma_part):
                cleaned = joined_part.strip(" \t-–—:：,、､/／")
                if cleaned:
                    members.append(cleaned)
        return members

    @staticmethod
    def _require_context(
        value: ContextValue | None,
        line_number: int,
        context_name: str,
    ) -> ContextValue:
        """メンバーの誤分類を防ぐため、構造上必要な文脈を要求する。"""

        if value is None:
            raise ParseError(
                f"line {line_number}: {context_name}を先に指定してください"
            )
        return value

    @staticmethod
    def _parse_member(
        line: str,
        alliance: str,
        tier: Tier,
        section_starts_at_21: bool,
        line_number: int,
    ) -> Member:
        """1人のメンバーと任意のインラインメタデータを抽出する。"""

        explicit_late_join = bool(LATE_JOIN_PATTERN.search(line))
        late_time = bool(LATE_TIME_PATTERN.search(line))
        starts_at_21 = section_starts_at_21 and not explicit_late_join and not late_time
        start_time, end_time = MarkdownMemberParser._parse_times(
            line,
            starts_at_21,
        )
        availability = MarkdownMemberParser._parse_availability(
            line,
            starts_at_21,
            end_time,
        )

        name = PARENTHETICAL_PATTERN.sub("", line)
        for pattern in (
            VC_PATTERN,
            MONTHLY_PATTERN,
            EARLY_LEAVE_PATTERN,
            EXPLICIT_START_PATTERN,
            SPECIAL_UNIT_PATTERN,
            LATE_JOIN_PATTERN,
            STANDALONE_TIME_PATTERN,
        ):
            name = pattern.sub("", name)
        name = name.strip(" \t-–—:：,、､/／")
        if not name:
            raise ParseError(f"line {line_number}: 参加者名が空です")

        return Member(
            name=name,
            alliance=alliance,
            tier=tier,
            has_vc=bool(VC_PATTERN.search(line)),
            starts_at_21=starts_at_21,
            availability=availability,
            special_unit=bool(SPECIAL_UNIT_PATTERN.search(line)),
            start_time_minutes=start_time,
            end_time_minutes=end_time,
        )

    @staticmethod
    def _parse_times(
        line: str,
        starts_at_21: bool,
    ) -> tuple[int | None, int | None]:
        """深夜0時以降を含む時刻を正規化した分単位で抽出する。"""

        times = [
            MarkdownMemberParser._clock_match_to_minutes(match)
            for match in CLOCK_PATTERN.finditer(line)
        ]
        if starts_at_21:
            return KVK_START_MINUTES, times[-1] if times else None
        if not times:
            return None, None
        return times[0], times[-1] if len(times) > 1 else None

    @staticmethod
    def _clock_match_to_minutes(match: re.Match[str]) -> int:
        """時、半時、または短縮時刻のトークンを分へ変換する。"""

        compact = match.group("compact")
        if compact:
            return int(compact[:2]) * MINUTES_PER_HOUR + int(compact[2:])
        hour = int(match.group("hour"))
        half_hour_minutes = MINUTES_PER_HOUR // 2 if match.group("half") else 0
        return hour * MINUTES_PER_HOUR + half_hour_minutes

    @staticmethod
    def _parse_availability(
        line: str,
        starts_at_21: bool,
        end_time_minutes: int | None,
    ) -> Availability:
        """終了時刻の注記を仕様で定めた優先度へ変換する。"""

        if not starts_at_21:
            return Availability.LATE_JOIN
        if LAST_UNTIL_PATTERN.search(line):
            return Availability.UNTIL_END
        if end_time_minutes is None:
            return (
                Availability.UNTIL_23
                if EARLY_LEAVE_PATTERN.search(line)
                else Availability.UNTIL_END
            )
        if end_time_minutes > UNTIL_24_MINUTES:
            return Availability.UNTIL_25
        if end_time_minutes > UNTIL_23_MINUTES:
            return Availability.UNTIL_24
        if end_time_minutes <= UNTIL_23_MINUTES:
            return Availability.UNTIL_23
        return Availability.UNTIL_END
