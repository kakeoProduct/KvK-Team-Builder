"""運用者の指定（settings.json）のJSON Repositoryのテスト。"""

import json
from pathlib import Path
from typing import Any

import pytest

from kvk_team.team_building.adapters.persistence.json_operator_settings_repository import (  # noqa: E501
    PLANNED_KEYS,
    JsonOperatorSettingsRepository,
    OperatorSettingsLoadError,
)
from kvk_team.team_building.domain.specification import (
    MemberRef,
    OperatorSpecification,
    SpecificationError,
)

LEADERS = [
    {"name": "ユウ", "alliance": "AAA"},
    {"name": "ミナ", "alliance": "BBB"},
    {"name": "ソラ", "alliance": "AAA"},
    {"name": "リク", "alliance": "DDD"},
]


def _load(tmp_path: Path, raw: Any, encoding: str = "utf-8") -> OperatorSpecification:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding=encoding)
    return JsonOperatorSettingsRepository(path).load()


def test_repository_reads_leaders_in_order(tmp_path: Path) -> None:
    """リーダー一覧を順のまま読み、順が隊の番号になる（FRM-001、DAT-007）。"""

    specification = _load(tmp_path, {"leaders": LEADERS})

    assert specification.leaders == (
        MemberRef("ユウ", "AAA"),
        MemberRef("ミナ", "BBB"),
        MemberRef("ソラ", "AAA"),
        MemberRef("リク", "DDD"),
    )
    assert specification.team_count == 4


def test_repository_accepts_utf8_with_bom(tmp_path: Path) -> None:
    """BOMつきのUTF-8も読む（DAT-002）。"""

    assert _load(tmp_path, {"leaders": LEADERS}, encoding="utf-8-sig").team_count == 4


def test_repository_rejects_non_utf8_file(tmp_path: Path) -> None:
    """UTF-8として読めないファイルは、ファイル名を示して入力のエラーにする（DAT-002）。"""

    path = tmp_path / "settings.json"
    path.write_bytes('{"leaders": [{"name": "ユウ"}]}'.encode("cp932"))

    with pytest.raises(
        OperatorSettingsLoadError, match="UTF-8として読めません.*settings.json"
    ):
        JsonOperatorSettingsRepository(path).load()


@pytest.mark.parametrize("key", sorted(PLANNED_KEYS))
def test_repository_rejects_specs_not_yet_supported(tmp_path: Path, key: str) -> None:
    """後のIssueで実装する指定は、黙って無視せずキーを示してエラーにする。"""

    with pytest.raises(
        OperatorSettingsLoadError, match=f"まだ対応していない指定があります: {key}"
    ):
        _load(tmp_path, {"leaders": LEADERS, key: None})


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({}, "settings: leadersがありません"),
        ({"leaders": LEADERS, "leader": []}, "settings: 未知の項目leader"),
        ({"leaders": "ユウ"}, "settings: leadersは配列"),
        (
            {"leaders": [*LEADERS[:2], {"name": "ソラ"}]},
            r"leadersの3番目: allianceがありません",
        ),
        (
            {"leaders": [*LEADERS[:2], {"name": "ソラ", "alliance": 1}]},
            r"leadersの3番目: allianceは文字列",
        ),
        (
            {"leaders": [*LEADERS[:2], {"name": " ", "alliance": "AAA"}]},
            r"leadersの3番目: メンバーの名前が空",
        ),
        (
            {"leaders": [*LEADERS[:2], {"name": "ソラ", "alliance": "AAA", "team": 3}]},
            r"leadersの3番目: 未知の項目team",
        ),
        ([], "settingsはオブジェクト"),
    ],
)
def test_repository_reports_location_of_each_error(
    tmp_path: Path, raw: Any, message: str
) -> None:
    """欠けた項目、型、書き間違えた項目の誤りを、どこの項目かを1回だけ示して伝える。"""

    with pytest.raises(OperatorSettingsLoadError, match=message) as raised:
        _load(tmp_path, raw)

    assert str(raised.value).count("leadersの3番目") <= 1


@pytest.mark.parametrize(
    ("leaders", "message"),
    [
        (
            [*LEADERS[:2], {"name": ["本物の名前"], "alliance": "AAA"}],
            r"leadersの3番目: nameは文字列",
        ),
        (
            [*LEADERS[:2], {"name": "本物の名前", "alliance": " "}],
            r"leadersの3番目: メンバーの同盟が空です",
        ),
        (
            [
                {"name": "本物の名前", "alliance": "AAA"},
                *LEADERS[1:3],
                {"name": "本物の名前", "alliance": "AAA"},
            ],
            "リーダー一覧の1番目と4番目が同じメンバーです",
        ),
    ],
)
def test_repository_error_does_not_echo_names(
    tmp_path: Path, leaders: list[Any], message: str
) -> None:
    """個人名がエラーから不具合報告へ漏れないよう、名前を示さず位置で示す（ADR 0026）。

    型の誤り、空の同盟、リーダーの重複の3つの経路を確かめる。
    """

    with pytest.raises(OperatorSettingsLoadError, match=message) as raised:
        _load(tmp_path, {"leaders": leaders})

    assert "本物の名前" not in str(raised.value)


def test_specification_requires_top_teams_and_unique_leaders() -> None:
    """上位隊の3人に満たないリーダー一覧と、同じリーダーの重複を拒否する。"""

    with pytest.raises(SpecificationError, match="3人以上"):
        OperatorSpecification(
            leaders=(MemberRef("ユウ", "AAA"), MemberRef("ミナ", "BBB"))
        )
    with pytest.raises(SpecificationError, match="1番目と3番目が同じメンバー"):
        OperatorSpecification(
            leaders=(
                MemberRef("ユウ", "AAA"),
                MemberRef("ミナ", "BBB"),
                MemberRef("ユウ", "AAA"),
            )
        )


def test_specification_error_in_file_is_reported_as_load_error(tmp_path: Path) -> None:
    """ファイルのリーダー一覧が成り立たない場合も、読み込みエラーとしてファイル名を示す。"""

    with pytest.raises(OperatorSettingsLoadError, match="settings.json.*3人以上"):
        _load(tmp_path, {"leaders": LEADERS[:2]})
