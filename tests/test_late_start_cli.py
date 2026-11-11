"""序盤に休止する隊を、番号付きの質問と回答のファイルで遅れて出撃させる統合テスト。

CLIから、Parser、回答の確認、Optimizer、Validator、Exporterまでを通す（FRM-041、FRM-075、FRM-090、
作成者の仮定A-41、ADR 0035）。名前は架空である。
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from deterministic_solver import deterministic_rules
from kvk_team.interfaces.cli import main as cli_main
from kvk_team.team_building.domain.rules import KvKRules

LEADERS = ["L1", "L2", "L3", "L4", "L5", "L6"]
RUN_AT = datetime(2026, 1, 1, 20, 52, 30, tzinfo=timezone(timedelta(hours=9)))
"""実行の時刻。出力のフォルダ名を決定的にする。"""
ROSTER = "\n".join(
    [
        "同盟名:TEST",
        "",
        "G8:",
        "L1◇",
        "L2◇",
        "L3◇",
        *(f"上位{index:02d}◇" for index in range(7)),
        "",
        "G7:",
        *(f"上位{index:02d}◇" for index in range(7, 14)),
        "",
        "G6:",
        *(f"上位{index:02d}◇" for index in range(14, 21)),
        "",
        "G5:",
        "L4◇",
        "L5◇",
        "L6◇（22-25）",
        *(f"後半{index}◇（22-25）" for index in range(4)),
        "",
    ]
)


@pytest.fixture
def event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """架空のイベントのフォルダを作り、CLIの探索設定を決定的にする。"""

    (tmp_path / "参加者一覧.md").write_text(ROSTER, encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        json.dumps(
            {"leaders": [{"name": name, "alliance": "TEST"} for name in LEADERS]}
        ),
        encoding="utf-8",
    )

    def rules(path: Path | None = None) -> KvKRules:
        return deterministic_rules()

    monkeypatch.setattr(cli_main, "default_rules", rules)
    return tmp_path


def _run(event: Path, *extra: str) -> int:
    arguments = [
        str(event / "参加者一覧.md"),
        str(event / "output"),
        "--settings",
        str(event / "settings.json"),
        *extra,
    ]
    try:
        return cli_main.main(arguments, clock=lambda: RUN_AT)
    except SystemExit as exit_info:
        return int(exit_info.code or 0)


def _markdown(event: Path) -> str:
    """出力のフォルダに書いた、ただ1つの実行の編成のMarkdownを返す。"""

    (folder,) = (event / "output").iterdir()
    return (folder / "チーム編成.md").read_text(encoding="utf-8")


def test_rest_in_opening_asks_numbered_question_with_exit_code_3(
    event: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """序盤に休止する隊があれば、番号付きの質問を示し、出力を書かずに3で終える。"""

    code = _run(event)

    error = capsys.readouterr().err
    assert code == 3
    assert "問1: 第6隊 21:00、21:30（序盤）" in error
    assert '"target": {"team": 6, "time": "21:00"}' in error
    assert not (event / "output").exists()


def test_answer_with_late_start_outputs_plan(
    event: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """問いの対象へ遅れて出撃させる回答を渡すと、出撃開始時刻を示して出力する。"""

    answers = event / "answers.json"
    answers.write_text(
        json.dumps(
            {
                "answers": [
                    {
                        "target": {"team": 6, "time": "21:00"},
                        "late_start": {"team": 6, "start": "22:00"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    code = _run(event, "--answers", str(answers))

    assert code == 0, capsys.readouterr().err
    markdown = _markdown(event)
    assert "出撃開始: 22:00（遅れて出撃）" in markdown
    assert "| 21:00 | 第6隊 | - | - | - | 出撃開始前 |" in markdown
    assert "- 必須条件: OK" in markdown
    assert "## 注記" not in markdown


def _write_answers(event: Path, *answers: tuple[int, str, int, str]) -> Path:
    path = event / "answers.json"
    path.write_text(
        json.dumps(
            {
                "answers": [
                    {
                        "target": {"team": target, "time": time},
                        "late_start": {"team": team, "start": start},
                    }
                    for target, time, team, start in answers
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_answer_to_target_without_shortfall_is_noted_in_output(
    event: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """下限を満たした対象への回答は使わず、出力の注記に示す（FRM-090の性質(3)、OUT-007）。"""

    answers = _write_answers(event, (6, "21:00", 6, "22:00"), (5, "21:00", 6, "22:00"))

    code = _run(event, "--answers", str(answers))

    assert code == 0, capsys.readouterr().err
    markdown = _markdown(event)
    assert (
        "## 注記\n\n- 注記: 第5隊 21:00への回答（第6隊を22:00から出撃）は" in markdown
    )
    assert "使いませんでした" in markdown


def test_delaying_team_whose_leader_joins_before_start_is_input_error(
    event: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """出撃開始前に参加するリーダーに応援先がなければ、理由を示して入力のエラー（2）にする。"""

    answers = _write_answers(event, (6, "21:00", 6, "22:00"), (6, "21:30", 5, "22:00"))

    code = _run(event, "--answers", str(answers))

    assert code == 2
    assert "第5隊のリーダー" in capsys.readouterr().err
    assert not (event / "output").exists()


def test_answer_with_supports_is_read_and_resolved_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """応援を持つ回答をファイルから読み、名前と同盟で参加者へ解決して確かめる（DAT-009）。

    第6隊と第7隊のリーダーは22:00から来て、序盤の参加者は1人だけのため、どちらかの隊が序盤に
    休止する。両方の隊に遅れて出撃させる回答を書き、休止した隊への回答を受け入れる。応援を持つ回答の
    対象（第5隊）は不足でないため、名前の解決と確認を通ったうえで使わなかったと注記する。
    この版の応援は休止を直せない（応援先が休止中でないことが条件のため）ため、応援を受け入れる
    統合テストは、序盤の8人（FRM-040）を加える分割案の4で足す。
    """

    roster = ROSTER.replace(
        "L6◇（22-25）", "L6◇（22-25）\nL7◇（22-25）\n早い人◇（21-22）"
    )
    (tmp_path / "参加者一覧.md").write_text(roster, encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        json.dumps(
            {
                "leaders": [
                    {"name": name, "alliance": "TEST"} for name in [*LEADERS, "L7"]
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli_main, "default_rules", lambda path=None: deterministic_rules()
    )
    support = [
        {"member": {"name": "早い人", "alliance": "TEST"}, "time": time, "team": 5}
        for time in ("21:00", "21:30")
    ]
    answers = tmp_path / "answers.json"
    answers.write_text(
        json.dumps(
            {
                "answers": [
                    {
                        "target": {"team": 6, "time": "21:00"},
                        "late_start": {"team": 6, "start": "22:00"},
                    },
                    {
                        "target": {"team": 7, "time": "21:00"},
                        "late_start": {"team": 7, "start": "22:00"},
                    },
                    {
                        "target": {"team": 5, "time": "21:00"},
                        "late_start": {"team": 6, "start": "22:00", "support": support},
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    code = _run(tmp_path, "--answers", str(answers))

    assert code == 0, capsys.readouterr().err
    markdown = _markdown(tmp_path)
    assert "出撃開始: 22:00（遅れて出撃）" in markdown
    notes = markdown.split("## 注記")[1].split("## 自己チェック")[0]
    assert "- 注記: 第5隊 21:00への回答（第6隊を22:00から出撃）は" in notes
    assert "早い人" not in notes


def test_previous_plan_from_shared_run_round_trips_without_changing_output(
    event: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """共有した回の編成のJSONを`--previous`で渡しても、同じ回答は受け入れられ、出力は変わらない。

    この版では前回の編成を編成に使わないため、回答を確かめる手順（作成者の仮定A-41の(5)）と
    FRM-090の性質(1)に影響しない（ADR 0036）。
    """

    answers = _write_answers(event, (6, "21:00", 6, "22:00"))
    assert _run(event, "--answers", str(answers)) == 0, capsys.readouterr().err
    (shared,) = (event / "output").iterdir()
    record = json.loads((shared / "チーム編成.json").read_text(encoding="utf-8"))
    sixth = next(team for team in record["teams"] if team["team"] == 6)
    assert sixth["start"] == "22:00"
    assert record["schema_version"] == 1
    assert record["created_at"] == "2026-01-01T20:52:30+09:00"
    capsys.readouterr()

    code = _run(
        event,
        "--answers",
        str(answers),
        "--previous",
        str(shared / "チーム編成.json"),
    )

    error = capsys.readouterr().err
    assert code == 0, error
    assert "編成には使いません" in error
    assert "参加者一覧（名前と同盟の組）にいません" not in error
    folders = sorted((event / "output").iterdir())
    assert [folder.name for folder in folders] == [
        "20260101-205230",
        "20260101-205230-2",
    ]
    first, second = (
        (folder / "チーム編成.md").read_text(encoding="utf-8") for folder in folders
    )
    assert first == second
    rerecorded = json.loads(
        (folders[1] / "チーム編成.json").read_text(encoding="utf-8")
    )
    del rerecorded["created_at"]
    del record["created_at"]
    assert rerecorded == record


def test_previous_plan_with_member_missing_from_roster_reports_count_only(
    event: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """前回の編成にいて今回の参加者一覧にいない人は、エラーにせず人数だけを示す（ADR 0036）。"""

    roster = event / "参加者一覧.md"
    roster.write_text(ROSTER.replace("L4◇", "L4◇\n抜けた人◇"), encoding="utf-8")
    answers = _write_answers(event, (6, "21:00", 6, "22:00"))
    assert _run(event, "--answers", str(answers)) == 0, capsys.readouterr().err
    (shared,) = (event / "output").iterdir()
    assert "抜けた人" in (shared / "チーム編成.json").read_text(encoding="utf-8")
    roster.write_text(ROSTER, encoding="utf-8")
    capsys.readouterr()

    code = _run(
        event,
        "--answers",
        str(answers),
        "--previous",
        str(shared / "チーム編成.json"),
    )

    error = capsys.readouterr().err
    assert code == 0, error
    assert "前回の編成の1人が、今回の参加者一覧（名前と同盟の組）にいません" in error
    assert "抜けた人" not in error


def test_previous_plan_does_not_change_numbered_questions(
    event: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """前回の編成を渡しても、回答が要る実行の問いは同じで、出力を書かない（作成者の仮定A-42の(2)）。

    今回の参加者一覧にいない人がいても、出力しない実行では人数を示さない（作成者の仮定A-42の(6)）。
    """

    roster = event / "参加者一覧.md"
    roster.write_text(ROSTER.replace("L4◇", "L4◇\n抜けた人◇"), encoding="utf-8")
    answers = _write_answers(event, (6, "21:00", 6, "22:00"))
    assert _run(event, "--answers", str(answers)) == 0, capsys.readouterr().err
    (shared,) = (event / "output").iterdir()
    roster.write_text(ROSTER, encoding="utf-8")
    capsys.readouterr()

    assert _run(event) == 3
    without_previous = capsys.readouterr().err
    assert _run(event, "--previous", str(shared / "チーム編成.json")) == 3
    with_previous = capsys.readouterr().err

    assert "問1: 第6隊 21:00、21:30（序盤）" in without_previous
    assert with_previous.endswith(without_previous)
    assert "編成には使いません" in with_previous
    assert "参加者一覧（名前と同盟の組）にいません" not in with_previous
    assert list((event / "output").iterdir()) == [shared]
