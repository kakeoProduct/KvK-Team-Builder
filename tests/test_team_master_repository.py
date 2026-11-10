"""JSONチームマスタRepositoryのテスト。"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from kvk_team.team_building.adapters.persistence.json_operator_settings_repository import (  # noqa: E501
    JsonOperatorSettingsRepository,
    default_settings_path,
)
from kvk_team.team_building.adapters.persistence.json_team_master_repository import (
    JsonTeamMasterRepository,
    TeamMasterLoadError,
    default_team_master_path,
    load_default_team_master,
)


def _write(tmp_path: Path, raw: dict[str, Any]) -> Path:
    path = tmp_path / "team_master.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


def _default_raw() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(
        default_team_master_path().read_text(encoding="utf-8")
    )
    return raw


def test_default_master_defines_event_time_and_member_cap() -> None:
    """既定マスタから戦闘時間と第4隊以降の上限を取得する。"""

    master = load_default_team_master()

    assert master.schema_version == 2
    assert master.event_time.start_minutes == 21 * 60
    assert master.event_time.end_minutes == 25 * 60
    assert master.event_time.slot_minutes == 30
    assert master.member_cap == 9


def test_repository_rejects_previous_schema_with_migration_guide(
    tmp_path: Path,
) -> None:
    """隊ごとの集結主を持つ以前の形は、黙って読まずに移し方を示して拒否する（ADR 0034）。"""

    path = _write(
        tmp_path, {"schema_version": 1, "teams": [], "strength_relations": []}
    )

    with pytest.raises(TeamMasterLoadError) as raised:
        JsonTeamMasterRepository(path).load()

    message = str(raised.value)
    assert "schema_version 2へ移してください" in message
    assert "settings.json" in message
    assert "leaders" in message
    assert "member_cap" in message


@pytest.mark.parametrize(
    ("field", "value"),
    [("start_time", 2100), ("end_time", None)],
)
def test_repository_rejects_wrongly_typed_event_fields(
    tmp_path: Path, field: str, value: object
) -> None:
    """イベント時間の型の誤りも、tracebackではなく読み込みエラーとして伝える。"""

    raw = _default_raw()
    raw["event"][field] = value

    with pytest.raises(TeamMasterLoadError, match=rf"event: {field}"):
        JsonTeamMasterRepository(_write(tmp_path, raw)).load()


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda raw: raw["event"].pop("start_time"), "event: start_timeがありません"),
        (
            lambda raw: raw["event"].update(start_time="2100"),
            "event: start_timeは「21:00」の形式",
        ),
        (lambda raw: raw["event"].update(start="21:00"), "event: 未知の項目start"),
        (
            lambda raw: raw["event"].update(slot_minutes=15),
            "event: 未知の項目slot_minutes",
        ),
        (
            lambda raw: raw["event"].update(end_time="24:45"),
            "30分の時間帯へ等分できる長さ",
        ),
        (
            lambda raw: raw["event"].update(start_time="21:15", end_time="25:15"),
            "30分の区切り",
        ),
        (lambda raw: raw.pop("member_cap"), "master: member_capがありません"),
        (lambda raw: raw.update(member_cap="9"), "master: member_capは整数"),
        (lambda raw: raw.update(member_cap=7), "上限は下限の8人以上"),
        (lambda raw: raw.update(teams=[]), "master: 未知の項目teams"),
        (lambda raw: raw.update(schema_version="2"), "master: schema_versionは整数"),
    ],
)
def test_repository_reports_location_of_each_error(
    tmp_path: Path, edit: Callable[[dict[str, Any]], object], message: str
) -> None:
    """欠けた項目、時刻の形式、書き間違えた項目、値の範囲の誤りも、どこの項目かを示す。"""

    raw = _default_raw()
    edit(raw)

    with pytest.raises(TeamMasterLoadError, match=message):
        JsonTeamMasterRepository(_write(tmp_path, raw)).load()


def test_repository_error_does_not_echo_field_values(tmp_path: Path) -> None:
    """本物の値がエラーから不具合報告へ漏れないよう、値を示さず型名だけを示す。"""

    raw = _default_raw()
    raw["member_cap"] = "本物の名前"

    with pytest.raises(TeamMasterLoadError) as error:
        JsonTeamMasterRepository(_write(tmp_path, raw)).load()

    assert "本物の名前" not in str(error.value)
    assert "（strが書かれています）" in str(error.value)


def test_bundled_master_uses_placeholder_roles_and_notes() -> None:
    """同梱の例は架空のリーダーだけを持ち、本物を載せない（ADR 0026、ADR 0034）。

    名前だけを本物へ書き換えても検出できるよう、架空の名前の一覧と完全に照合する。
    チームマスタは名前を持たず、リーダー一覧は運用者の指定の例にだけ置く。
    """

    specification = JsonOperatorSettingsRepository(default_settings_path()).load()

    assert [(ref.name, ref.alliance) for ref in specification.leaders] == [
        ("山田", "SKY"),
        ("さくら", "FOX"),
        ("taro", "SUN"),
        ("わんこ", "SKY"),
        ("もーもー", "MOON"),
        ("いろは", "SKY"),
        ("ハルカ", "SUN"),
        ("mt", "FOX"),
        ("もも", "MOON"),
        ("ミカン", "SUN"),
        ("翡翠", "MOON"),
    ]
    assert set(_default_raw()) == {"schema_version", "event", "member_cap"}
