"""運用者の回答（answers.json）のJSON Repositoryのテスト（DAT-009、作成者の仮定A-41）。"""

import json
from pathlib import Path
from typing import Any

import pytest

from kvk_team.team_building.adapters.persistence.json_answers_repository import (
    AnswersLoadError,
    JsonAnswersRepository,
)
from kvk_team.team_building.domain.answers import Answer
from kvk_team.team_building.domain.specification import (
    LateStart,
    MemberRef,
    SupportRef,
)

SUPPORT = {
    "member": {"name": "カイ", "alliance": "AAA"},
    "time": "21:00",
    "team": 7,
}
ANSWER = {
    "target": {"team": 7, "time": "21:00"},
    "late_start": {"team": 10, "start": "22:00", "support": [SUPPORT]},
}


def _load(tmp_path: Path, raw: Any, encoding: str = "utf-8") -> tuple[Answer, ...]:
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding=encoding)
    return JsonAnswersRepository(path).load()


def test_repository_reads_target_late_start_and_supports(tmp_path: Path) -> None:
    """問いの対象と、遅れて出撃する隊、出撃開始時刻、応援先を読む。"""

    answers = _load(tmp_path, {"answers": [ANSWER]})

    assert answers == (
        Answer(
            target_team=7,
            target_slot_start=21 * 60,
            late_start=LateStart(
                10, 22 * 60, (SupportRef(MemberRef("カイ", "AAA"), 21 * 60, 7),)
            ),
        ),
    )


def test_repository_reads_late_start_without_supports_and_bom(tmp_path: Path) -> None:
    """応援のない遅れて出撃する隊を書け、BOM付きのUTF-8も読む（DAT-002）。"""

    raw = {
        "answers": [
            {
                "target": {"team": 10, "time": "21:30"},
                "late_start": {"team": 10, "start": "24:30"},
            }
        ]
    }

    answers = _load(tmp_path, raw, encoding="utf-8-sig")

    assert answers[0].late_start == LateStart(10, 24 * 60 + 30)
    assert answers[0].target_slot_start == 21 * 60 + 30


def test_repository_reads_empty_answers(tmp_path: Path) -> None:
    """回答のない一覧を読める。"""

    assert _load(tmp_path, {"answers": []}) == ()


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({}, "answersがありません"),
        ({"answers": {}}, "配列"),
        ({"answers": [], "extra": 1}, "未知の項目extra"),
        ({"answers": [{**ANSWER, "number": 1}]}, "未知の項目number"),
        ({"answers": [{"target": ANSWER["target"]}]}, "late_startがありません"),
        (
            {"answers": [{**ANSWER, "target": {"team": "7", "time": "21:00"}}]},
            "整数",
        ),
        (
            {"answers": [{**ANSWER, "target": {"team": 7, "time": "9時"}}]},
            "「21:00」の形式",
        ),
        (
            {
                "answers": [
                    {
                        **ANSWER,
                        "late_start": {
                            "team": 10,
                            "start": "22:00",
                            "support": [{**SUPPORT, "member": {"name": ""}}],
                        },
                    }
                ]
            },
            "allianceがありません",
        ),
        (
            {
                "answers": [
                    {
                        **ANSWER,
                        "late_start": {
                            "team": 10,
                            "start": "22:00",
                            "support": [SUPPORT, SUPPORT],
                        },
                    }
                ]
            },
            "同じメンバーの同じ時間帯",
        ),
    ],
)
def test_repository_rejects_invalid_answers_without_names(
    tmp_path: Path, raw: Any, message: str
) -> None:
    """誤りは位置とキーを示して読み込みエラーにし、名前を出さない（ADR 0026）。"""

    with pytest.raises(AnswersLoadError, match=message) as raised:
        _load(tmp_path, raw)
    assert "カイ" not in str(raised.value)


def test_repository_rejects_non_utf8(tmp_path: Path) -> None:
    """UTF-8として読めないファイルは、ファイル名を示して読み込みエラーにする（DAT-002）。"""

    path = tmp_path / "answers.json"
    path.write_bytes('{"answers": []}　'.encode("cp932"))

    with pytest.raises(AnswersLoadError, match="UTF-8"):
        JsonAnswersRepository(path).load()


def test_repository_reports_missing_file(tmp_path: Path) -> None:
    """ファイルがなければ、パスを示して読み込みエラーにする。"""

    with pytest.raises(AnswersLoadError, match="answers.json"):
        JsonAnswersRepository(tmp_path / "answers.json").load()
