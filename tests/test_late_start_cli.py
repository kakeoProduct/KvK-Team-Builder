"""序盤に休止する隊を、番号付きの質問と回答のファイルで遅れて出撃させる統合テスト。

CLIから、Parser、回答の確認、Optimizer、Validator、Exporterまでを通す（FRM-041、FRM-075、FRM-090、
作成者の仮定A-41、ADR 0035）。名前は架空である。
"""

import json
from pathlib import Path

import pytest

from deterministic_solver import deterministic_rules
from kvk_team.interfaces.cli import main as cli_main
from kvk_team.team_building.domain.rules import KvKRules

LEADERS = ["L1", "L2", "L3", "L4", "L5", "L6"]
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
        str(event / "チーム編成.md"),
        "--settings",
        str(event / "settings.json"),
        *extra,
    ]
    try:
        return cli_main.main(arguments)
    except SystemExit as exit_info:
        return int(exit_info.code or 0)


def test_rest_in_opening_asks_numbered_question_with_exit_code_3(
    event: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """序盤に休止する隊があれば、番号付きの質問を示し、出力を書かずに3で終える。"""

    code = _run(event)

    error = capsys.readouterr().err
    assert code == 3
    assert "問1: 第6隊 21:00、21:30（序盤）" in error
    assert '"target": {"team": 6, "time": "21:00"}' in error
    assert not (event / "チーム編成.md").exists()


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
    markdown = (event / "チーム編成.md").read_text(encoding="utf-8")
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
    markdown = (event / "チーム編成.md").read_text(encoding="utf-8")
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
    assert not (event / "チーム編成.md").exists()


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
    markdown = (tmp_path / "チーム編成.md").read_text(encoding="utf-8")
    assert "出撃開始: 22:00（遅れて出撃）" in markdown
    notes = markdown.split("## 注記")[1].split("## 自己チェック")[0]
    assert "- 注記: 第5隊 21:00への回答（第6隊を22:00から出撃）は" in notes
    assert "早い人" not in notes
