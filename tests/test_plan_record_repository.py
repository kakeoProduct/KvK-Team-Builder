"""編成のJSON（DAT-010）のRepositoryのテスト。書いたJSONを前回の編成として読み戻せることを確かめる。

名前は架空である。
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given

from kvk_team.team_building.adapters.persistence.json_plan_record_repository import (
    JsonPlanRecordRepository,
    PlanRecordLoadError,
    parse_plan_record,
    render_plan_record,
)
from kvk_team.team_building.domain.plan_record import (
    PlanRecord,
    RecordedMember,
    RecordedTeam,
)
from kvk_team.team_building.domain.specification import MemberRef, SupportRef
from kvk_team.team_building.domain.validation import (
    TeamPlanValidator,
    ValidatedTeamPlan,
)
from team_plan_strategies import RULES, Scenario, scenarios

JST = timezone(timedelta(hours=9))
YUU = {"name": "ユウ", "alliance": "AAA"}
KAI = {"name": "カイ", "alliance": "AAA"}
MINA = {"name": "ミナ", "alliance": "BBB"}
SORA = {"name": "ソラ", "alliance": "AAA"}
RIKU = {"name": "リク", "alliance": "DDD"}
NAGI = {"name": "ナギ", "alliance": "BBB"}
REN = {"name": "レン", "alliance": "BBB"}
SAKI = {"name": "サキ", "alliance": "DDD"}


def _document(**changes: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": 1,
        "created_at": "2026-01-01T21:52:30+09:00",
        "teams": [
            {"team": 1, "leader": YUU, "start": None, "members": [YUU]},
            {"team": 2, "leader": MINA, "start": None, "members": [MINA]},
            {"team": 3, "leader": SORA, "start": None, "members": [SORA]},
            {"team": 5, "leader": NAGI, "start": None, "members": [NAGI]},
            {"team": 6, "leader": RIKU, "start": "22:00", "members": [RIKU, KAI]},
        ],
        "supports": [{"member": KAI, "time": "21:00", "team": 5}],
        "waiting": [{"member": REN}],
        "undecided": [{"member": SAKI}],
    }
    document.update(changes)
    return document


def _write(tmp_path: Path, raw: Any, encoding: str = "utf-8") -> Path:
    path = tmp_path / "チーム編成.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding=encoding)
    return path


def _ref(raw: dict[str, str]) -> MemberRef:
    return MemberRef(raw["name"], raw["alliance"])


EXPECTED = PlanRecord(
    created_at=datetime(2026, 1, 1, 21, 52, 30, tzinfo=JST),
    teams=(
        RecordedTeam(1, _ref(YUU), (_ref(YUU),)),
        RecordedTeam(2, _ref(MINA), (_ref(MINA),)),
        RecordedTeam(3, _ref(SORA), (_ref(SORA),)),
        RecordedTeam(5, _ref(NAGI), (_ref(NAGI),)),
        RecordedTeam(6, _ref(RIKU), (_ref(RIKU), _ref(KAI)), start_minutes=22 * 60),
    ),
    supports=(SupportRef(_ref(KAI), 21 * 60, 5),),
    waiting=(RecordedMember(_ref(REN)),),
    undecided=(RecordedMember(_ref(SAKI)),),
)


def test_repository_reads_plan_record(tmp_path: Path) -> None:
    """所属、出撃開始時刻、応援、待機、別枠と、時差付きの出力時刻を読む。"""

    assert JsonPlanRecordRepository(_write(tmp_path, _document())).load() == EXPECTED


def test_repository_reads_bom_and_destination_alliances(tmp_path: Path) -> None:
    """BOM付きのUTF-8を読み（DAT-002）、総力モードの移動先（FRM-071）を隊と待機・別枠で読む。"""

    document = _document()
    document["teams"][0]["destination_alliance"] = "AAA"
    document["undecided"][0]["destination_alliance"] = "BBB"

    record = JsonPlanRecordRepository(
        _write(tmp_path, document, encoding="utf-8-sig")
    ).load()

    assert record.teams[0].destination_alliance == "AAA"
    assert record.undecided[0].destination_alliance == "BBB"
    assert record.waiting[0].destination_alliance is None


def test_rendered_json_round_trips_and_omits_unset_destinations(tmp_path: Path) -> None:
    """書いたJSONは読み戻すと同じ記録になる。名前はエスケープせず、未設定の移動先は書かない。"""

    text = render_plan_record(EXPECTED)

    assert json.loads(text) == _document()
    assert "ユウ" in text
    assert text.endswith("\n")
    path = tmp_path / "チーム編成.json"
    path.write_text(text, encoding="utf-8")
    assert JsonPlanRecordRepository(path).load() == EXPECTED


def test_rendered_json_writes_destinations_and_late_clock() -> None:
    """移動先がある記録はその欄を書き、24時以降の時刻は24:30の形で書く（ROS-022）。"""

    record = PlanRecord(
        created_at=EXPECTED.created_at,
        teams=(
            RecordedTeam(1, _ref(YUU), (_ref(YUU),), destination_alliance="AAA"),
            RecordedTeam(6, _ref(RIKU), (_ref(RIKU),), start_minutes=24 * 60 + 30),
        ),
        waiting=(RecordedMember(_ref(REN), destination_alliance="BBB"),),
    )

    raw = json.loads(render_plan_record(record))

    assert raw["teams"][0]["destination_alliance"] == "AAA"
    assert raw["teams"][1]["start"] == "24:30"
    assert raw["waiting"] == [{"member": REN, "destination_alliance": "BBB"}]
    assert raw["supports"] == []
    assert raw["undecided"] == []


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (_document(schema_version=2), "schema_versionは1"),
        (
            {
                key: value
                for key, value in _document().items()
                if key != "schema_version"
            },
            "schema_versionがありません",
        ),
        (_document(extra=1), "未知の項目extra"),
        (_document(created_at="2026-01-01T21:52:30"), "created_atに時差がありません"),
        (_document(created_at="昨日"), "created_atは時差付きのISO 8601"),
        (_document(teams={}), "teamsは配列"),
        (
            _document(
                teams=[
                    {"team": 1, "leader": YUU, "start": None, "members": [YUU], "x": 1}
                ]
            ),
            "teamsの1番目: 未知の項目x",
        ),
        (
            _document(
                teams=[{"team": "1", "leader": YUU, "start": None, "members": [YUU]}]
            ),
            "teamsの1番目: teamは整数",
        ),
        (
            _document(
                teams=[{"team": 1, "leader": YUU, "start": "夜", "members": [YUU]}]
            ),
            "teamsの1番目: startは「21:00」の形式",
        ),
        (
            _document(waiting=[{"member": {"name": "", "alliance": "BBB"}}]),
            "waitingの1番目のmember: メンバーの名前が空です",
        ),
        (
            _document(waiting=[{"member": REN, "destination_alliance": 1}]),
            "waitingの1番目: destination_allianceは文字列",
        ),
        (
            _document(undecided=[{"member": SAKI, "destination_alliance": None}]),
            "undecidedの1番目: destination_allianceは文字列",
        ),
        (
            _document(waiting=[{"member": YUU}]),
            "同じメンバーが第1隊の所属と待機にいます",
        ),
    ],
)
def test_repository_reports_invalid_json_with_position_without_names(
    tmp_path: Path, document: Any, message: str
) -> None:
    """形の誤りと成り立たない記録を、パスと位置を示し、名前を書かずに読み込みエラーにする。"""

    path = _write(tmp_path, document)

    with pytest.raises(PlanRecordLoadError) as error:
        JsonPlanRecordRepository(path).load()

    text = str(error.value)
    assert message in text
    assert str(path) in text
    for name in ("ユウ", "カイ", "ミナ", "ソラ", "リク", "レン", "サキ", "ナギ"):
        assert name not in text


def test_repository_reports_unreadable_files(tmp_path: Path) -> None:
    """ない、UTF-8でない、JSONでないファイルを、パスを示して読み込みエラーにする。"""

    missing = tmp_path / "ない.json"
    not_utf8 = tmp_path / "cp932.json"
    not_utf8.write_bytes('{"teams": "ユウ"}'.encode("cp932"))
    broken = tmp_path / "壊れた.json"
    broken.write_text("{", encoding="utf-8")

    for path, message in (
        (missing, "前回の編成を読み込めません"),
        (not_utf8, "前回の編成をUTF-8として読めません"),
        (broken, "前回の編成を読み込めません"),
    ):
        with pytest.raises(PlanRecordLoadError) as error:
            JsonPlanRecordRepository(path).load()
        assert message in str(error.value)
        assert str(path) in str(error.value)


@given(scenarios())
def test_any_valid_plan_round_trips_through_json(scenario: Scenario) -> None:
    """必須条件を満たす編成の記録は、JSONに書いて読み戻すと同じ記録になり、全員が参加者一覧に当たる。"""

    plan = scenario.plan()
    report = TeamPlanValidator(RULES).validate(
        plan, scenario.source_members, scenario.specification
    )
    validated = ValidatedTeamPlan(plan=plan, report=report, proven_optimal=True)
    record = PlanRecord.from_validated(validated, EXPECTED.created_at)

    assert parse_plan_record(json.loads(render_plan_record(record))) == record
    assert record.unmatched_count(scenario.source_members) == 0
    assert sum(1 for _ in record.members()) == len(scenario.source_members)


def test_rendered_created_at_is_written_to_seconds() -> None:
    """実行の時刻はマイクロ秒を持つが、`created_at`は秒までの時差付きのISO 8601で書く。"""

    record = PlanRecord(
        created_at=EXPECTED.created_at.replace(microsecond=123456),
        teams=EXPECTED.teams,
    )

    raw = json.loads(render_plan_record(record))

    assert raw["created_at"] == "2026-01-01T21:52:30+09:00"
