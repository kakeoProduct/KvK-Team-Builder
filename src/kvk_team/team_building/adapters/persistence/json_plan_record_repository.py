"""編成のJSON（DAT-010）のRepository。出力した編成を書き、前回の編成（`--previous`）として読む。

境界は`application.ports.PlanRecordRepository`。編成のJSONは個人名を含むため、イベントのフォルダの
`output/`（Git管理外）に置く（DAT-001、DAT-008）。誤りのメッセージには名前を出さず、キーと位置だけを
示す。アダプターは形式の変換だけを行い、記録が成り立つかはドメインの`PlanRecord`が確かめる。
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from kvk_team.team_building.adapters.persistence.json_operator_settings_repository import (  # noqa: E501
    parse_member_ref,
)
from kvk_team.team_building.adapters.persistence.json_team_master_repository import (
    JsonFields,
)
from kvk_team.team_building.domain.plan_record import (
    PlanRecord,
    RecordedMember,
    RecordedTeam,
)
from kvk_team.team_building.domain.specification import MemberRef, SupportRef
from kvk_team.team_building.domain.validation import format_clock

SCHEMA_VERSION = 1
"""編成のJSONの版。形を変えたら上げ、古い版は読み込みエラーにする。"""


class PlanRecordLoadError(ValueError):
    """前回の編成を安全に読み込めない場合に送出する。"""


@dataclass(frozen=True, slots=True)
class JsonPlanRecordRepository:
    """編成のJSONから編成の記録を構築するRepository。"""

    path: Path

    def load(self) -> PlanRecord:
        """JSONを読み込み、編成の記録を返す。UTF-8のBOMの有無の両方を受け付ける（DAT-002）。"""

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
            return parse_plan_record(raw)
        except UnicodeDecodeError as error:
            raise PlanRecordLoadError(
                f"前回の編成をUTF-8として読めません: {self.path}"
            ) from error
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise PlanRecordLoadError(
                f"前回の編成を読み込めません: {self.path}: {error}"
            ) from error


def render_plan_record(record: PlanRecord) -> str:
    """編成の記録を、UTF-8で書くJSONの文字列にする。名前はエスケープしない。"""

    document = {
        "schema_version": SCHEMA_VERSION,
        "created_at": record.created_at.isoformat(timespec="seconds"),
        "teams": [_render_team(team) for team in record.teams],
        "supports": [
            {
                "member": _render_ref(support.member),
                "time": format_clock(support.slot_start_minutes),
                "team": support.team,
            }
            for support in record.supports
        ],
        "waiting": [_render_seat(seat) for seat in record.waiting],
        "undecided": [_render_seat(seat) for seat in record.undecided],
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def parse_plan_record(raw: Any) -> PlanRecord:
    """JSONオブジェクトを編成の記録へ変換する。"""

    document = JsonFields(raw, "編成のJSON")
    document.reject_unknown(
        frozenset(
            {
                "schema_version",
                "created_at",
                "teams",
                "supports",
                "waiting",
                "undecided",
            }
        )
    )
    version = document.integer("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"編成のJSON: schema_versionは{SCHEMA_VERSION}だけを読めます"
            f"（{version}が書かれています）"
        )
    return PlanRecord(
        created_at=_created_at(document.string("created_at")),
        teams=tuple(
            _team(item, f"teamsの{index}番目")
            for index, item in enumerate(document.items("teams"), start=1)
        ),
        supports=tuple(
            _support(item, f"supportsの{index}番目")
            for index, item in enumerate(document.items("supports"), start=1)
        ),
        waiting=_seats(document, "waiting"),
        undecided=_seats(document, "undecided"),
    )


def _created_at(text: str) -> datetime:
    """実行の時刻を読む。時差がないかは`PlanRecord`が確かめる（DAT-002）。"""

    try:
        return datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError(
            "編成のJSON: created_atは時差付きのISO 8601で書いてください"
        ) from error


def _team(raw: Any, where: str) -> RecordedTeam:
    fields = JsonFields(raw, where)
    fields.reject_unknown(
        frozenset({"team", "leader", "start", "members", "destination_alliance"})
    )
    start = None if fields.value("start") is None else fields.clock("start")
    return RecordedTeam(
        number=fields.integer("team"),
        leader=parse_member_ref(fields.value("leader"), f"{where}のleader"),
        members=tuple(
            parse_member_ref(item, f"{where}のmembersの{index}番目")
            for index, item in enumerate(fields.items("members"), start=1)
        ),
        start_minutes=start,
        destination_alliance=_destination(fields),
    )


def _support(raw: Any, where: str) -> SupportRef:
    fields = JsonFields(raw, where)
    fields.reject_unknown(frozenset({"member", "time", "team"}))
    return SupportRef(
        member=parse_member_ref(fields.value("member"), f"{where}のmember"),
        slot_start_minutes=fields.clock("time"),
        team=fields.integer("team"),
    )


def _seats(document: JsonFields, key: str) -> tuple[RecordedMember, ...]:
    result = []
    for index, item in enumerate(document.items(key), start=1):
        where = f"{key}の{index}番目"
        fields = JsonFields(item, where)
        fields.reject_unknown(frozenset({"member", "destination_alliance"}))
        result.append(
            RecordedMember(
                member=parse_member_ref(fields.value("member"), f"{where}のmember"),
                destination_alliance=_destination(fields),
            )
        )
    return tuple(result)


def _destination(fields: JsonFields) -> str | None:
    if "destination_alliance" not in fields.raw:
        return None
    return fields.string("destination_alliance")


def _render_ref(ref: MemberRef) -> dict[str, str]:
    return {"name": ref.name, "alliance": ref.alliance}


def _render_team(team: RecordedTeam) -> dict[str, Any]:
    rendered: dict[str, Any] = {
        "team": team.number,
        "leader": _render_ref(team.leader),
        "start": None
        if team.start_minutes is None
        else format_clock(team.start_minutes),
        "members": [_render_ref(member) for member in team.members],
    }
    if team.destination_alliance is not None:
        rendered["destination_alliance"] = team.destination_alliance
    return rendered


def _render_seat(seat: RecordedMember) -> dict[str, Any]:
    rendered: dict[str, Any] = {"member": _render_ref(seat.member)}
    if seat.destination_alliance is not None:
        rendered["destination_alliance"] = seat.destination_alliance
    return rendered
