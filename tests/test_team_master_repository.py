"""JSONチームマスタRepositoryのテスト。"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from kvk_team.team_building.adapters.persistence.json_team_master_repository import (
    JsonTeamMasterRepository,
    TeamMasterLoadError,
    default_team_master_path,
    load_default_team_master,
)
from kvk_team.team_building.domain.team import TeamLabel
from kvk_team.team_building.domain.team_master import StrengthOperator


def test_default_master_defines_leaders_capacity_and_strength_relations() -> None:
    """既定マスタから動的編成に必要なルールをすべて取得する。"""

    master = load_default_team_master()

    assert master.rally_leaders[TeamLabel.G] == "ハルカ"
    assert master.rally_leaders[TeamLabel.K] == "翡翠"
    assert master.teams_by_label[TeamLabel.A].maximum_members == 8
    assert master.teams_by_label[TeamLabel.F].maximum_members == 9
    assert master.teams_by_label[TeamLabel.H].substitute_leaders == ("らいおん",)
    assert master.strength_relations[0].operator is StrengthOperator.GREATER_THAN
    assert (
        master.strength_relations[1].operator is StrengthOperator.GREATER_THAN_OR_EQUAL
    )


def test_repository_rejects_incomplete_json_master(tmp_path: Path) -> None:
    """必須フィールドがないJSONをドメインへ渡さない。"""

    path = tmp_path / "team_master.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    with pytest.raises(TeamMasterLoadError, match="チームマスタ"):
        JsonTeamMasterRepository(path).load()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("vc_required", "false"),
        ("substitute_leaders", "らいおん"),
        ("notes", "運用メモの例"),
        ("substitute_leaders", ["らいおん", 1]),
        ("rally_leader", None),
        ("rally_leader", ["山田"]),
        ("role", 1),
        ("maximum_members", "9"),
        ("minimum_members", True),
        ("minimum_members", 8.5),
    ],
)
def test_repository_rejects_wrongly_typed_team_fields(
    tmp_path: Path, field: str, value: object
) -> None:
    """手で編集した本物のマスタの型の誤りを、黙って別の規則として読まない（ADR 0026）。

    どのチームの誤りかを探さずに済むよう、メッセージにチームラベルを含める。
    """

    raw = json.loads(default_team_master_path().read_text(encoding="utf-8"))
    raw["teams"][7][field] = value
    path = tmp_path / "team_master.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(TeamMasterLoadError, match=rf"H: {field}"):
        JsonTeamMasterRepository(path).load()


@pytest.mark.parametrize(
    ("field", "value"),
    [("start_time", 2100), ("end_time", None), ("slot_minutes", "30")],
)
def test_repository_rejects_wrongly_typed_event_fields(
    tmp_path: Path, field: str, value: object
) -> None:
    """イベント時間の型の誤りも、tracebackではなく読み込みエラーとして伝える。"""

    raw = json.loads(default_team_master_path().read_text(encoding="utf-8"))
    raw["event"][field] = value
    path = tmp_path / "team_master.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(TeamMasterLoadError, match=rf"event: {field}"):
        JsonTeamMasterRepository(path).load()


def test_repository_reports_missing_and_unknown_team_fields_with_label(
    tmp_path: Path,
) -> None:
    """欠けた項目と書き間違えた項目を、黙って空として読まずにチームラベル付きで報告する。"""

    raw = json.loads(default_team_master_path().read_text(encoding="utf-8"))
    path = tmp_path / "team_master.json"

    missing = json.loads(json.dumps(raw))
    del missing["teams"][7]["role"]
    path.write_text(json.dumps(missing, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(TeamMasterLoadError, match="H: roleがありません"):
        JsonTeamMasterRepository(path).load()

    misspelled = json.loads(json.dumps(raw))
    misspelled["teams"][7]["substitute_leader"] = misspelled["teams"][7].pop(
        "substitute_leaders"
    )
    path.write_text(json.dumps(misspelled, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(TeamMasterLoadError, match="H: 未知の項目substitute_leader"):
        JsonTeamMasterRepository(path).load()


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        (None, "schema_version", "1", "master: schema_version"),
        ("event", "start_time", "2100", "event: start_time"),
    ],
)
def test_repository_reports_master_and_clock_errors_with_location(
    tmp_path: Path, section: str | None, field: str, value: object, message: str
) -> None:
    """マスタ全体の項目と時刻の形式の誤りも、どこの項目かを示す。"""

    raw = json.loads(default_team_master_path().read_text(encoding="utf-8"))
    (raw if section is None else raw[section])[field] = value
    path = tmp_path / "team_master.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(TeamMasterLoadError, match=message):
        JsonTeamMasterRepository(path).load()


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda raw: raw["event"].pop("start_time"), "event: start_timeがありません"),
        (
            lambda raw: raw["event"].update(start_time="2100"),
            "event: start_timeは「21:00」の形式",
        ),
        (
            lambda raw: raw["strength_relations"][1].pop("operator"),
            r"strength_relations\[2\]: operatorがありません",
        ),
        (lambda raw: raw.pop("teams"), "master: teamsがありません"),
        (
            lambda raw: raw["teams"][7].update(maximum_members=1),
            "H: チームの最大人数",
        ),
    ],
)
def test_repository_reports_location_of_each_error(
    tmp_path: Path, edit: Callable[[dict[str, Any]], object], message: str
) -> None:
    """欠けた項目、時刻の形式、戦力関係、値の範囲の誤りも、どこの項目かを示す。"""

    raw = json.loads(default_team_master_path().read_text(encoding="utf-8"))
    edit(raw)
    path = tmp_path / "team_master.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(TeamMasterLoadError, match=message):
        JsonTeamMasterRepository(path).load()


@pytest.mark.parametrize(
    ("edit", "kind"),
    [
        (
            lambda raw: raw["teams"][7].update(substitute_leaders="本物の名前"),
            "（strが書かれています）",
        ),
        (lambda raw: raw["teams"][7].update(label="本物の名前"), "A〜K"),
        (
            lambda raw: raw["strength_relations"][0].update(operator="本物の名前"),
            "operator",
        ),
    ],
)
def test_repository_error_does_not_echo_field_values(
    tmp_path: Path, edit: Callable[[dict[str, Any]], object], kind: str
) -> None:
    """本物のマスタの名前がエラーから不具合報告へ漏れないよう、値を示さない。"""

    raw = json.loads(default_team_master_path().read_text(encoding="utf-8"))
    edit(raw)
    path = tmp_path / "team_master.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(TeamMasterLoadError) as error:
        JsonTeamMasterRepository(path).load()

    assert "本物の名前" not in str(error.value)
    assert kind in str(error.value)


def test_bundled_master_uses_placeholder_roles_and_notes() -> None:
    """同梱の例は集結主、代理集結主、役割、運用メモを架空にし、本物を載せない（ADR 0026）。

    名前だけを本物へ書き換えても検出できるよう、架空の名前の一覧と完全に照合する。
    """

    master = load_default_team_master()

    assert {team.label.value: team.rally_leader for team in master.teams} == {
        "A": "山田",
        "B": "さくら",
        "C": "taro",
        "D": "わんこ",
        "E": "もーもー",
        "F": "いろは",
        "G": "ハルカ",
        "H": "mt",
        "I": "もも",
        "J": "ミカン",
        "K": "翡翠",
    }
    assert {
        team.label.value: team.substitute_leaders
        for team in master.teams
        if team.substitute_leaders
    } == {"H": ("らいおん",)}
    assert [team.role for team in master.teams] == [
        f"役割{team.label.value}" for team in master.teams
    ]
    assert {note for team in master.teams for note in team.notes} <= {"運用メモの例"}
