"""CLIの組み立て、起動経路、同梱データの設定を検証する。"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from deterministic_solver import deterministic_rules
from kvk_team.interfaces.cli import main as cli_main
from kvk_team.interfaces.cli.composition import (
    create_team_builder,
    default_rules,
    default_specification,
)
from kvk_team.team_building.adapters.optimization.errors import (
    OptimizationTimeoutError,
)
from kvk_team.team_building.adapters.persistence.json_operator_settings_repository import (  # noqa: E501
    default_settings_path,
)
from kvk_team.team_building.adapters.persistence.json_team_master_repository import (  # noqa: E501
    TeamMasterLoadError,
    default_team_master_path,
    load_default_team_master,
)
from kvk_team.team_building.application.build_team_plan import (
    BuildError,
    BuildTeamPlan,
    LowerBoundShortfallError,
    NoValidPlanError,
    ShortfallQuestion,
    ShortfallUndeterminedError,
)
from kvk_team.team_building.domain.answers import Answer
from kvk_team.team_building.domain.plan import TimeSlot
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.specification import (
    MemberRef,
    OperatorSpecification,
)
from kvk_team.team_building.domain.validation import ValidationCode, ValidationIssue

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
ROSTER = "同盟名:SKY\nG8:\n山田◯◇\n"


def _pyproject() -> dict:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as source:
        return tomllib.load(source)


def _input(tmp_path: Path) -> Path:
    path = tmp_path / "参加者一覧.md"
    path.write_text(ROSTER, encoding="utf-8")
    return path


def _write_settings(path: Path, leaders: list[tuple[str, str]]) -> None:
    raw = {
        "leaders": [{"name": name, "alliance": alliance} for name, alliance in leaders]
    }
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")


class RecordingBuilder:
    """組み立てに渡したルールと、buildに渡した指定を記録する。"""

    rules: list[KvKRules] = []
    specifications: list[OperatorSpecification] = []
    answers: list[tuple[Answer, ...]] = []

    def __init__(self, rules: KvKRules) -> None:
        RecordingBuilder.rules.append(rules)

    def build(
        self,
        markdown: str,
        specification: OperatorSpecification,
        answers: tuple[Answer, ...] = (),
    ) -> str:
        RecordingBuilder.specifications.append(specification)
        RecordingBuilder.answers.append(tuple(answers))
        return "出力\n"


@pytest.fixture
def recording_builder(monkeypatch: pytest.MonkeyPatch) -> type[RecordingBuilder]:
    RecordingBuilder.rules = []
    RecordingBuilder.specifications = []
    RecordingBuilder.answers = []
    monkeypatch.setattr(cli_main, "create_team_builder", RecordingBuilder)
    return RecordingBuilder


def test_create_team_builder_shares_given_rules_with_all_parts() -> None:
    """渡した編成ルールを、Optimizer、Validator、Exporterが共有する。"""

    rules = deterministic_rules()
    builder = create_team_builder(rules)

    use_case = builder.build_team_plan
    assert isinstance(use_case, BuildTeamPlan)
    assert use_case.rules is rules
    assert use_case.optimizer.rules is rules  # type: ignore[attr-defined]
    assert use_case.validator.rules is rules  # type: ignore[attr-defined]
    assert builder.exporter.rules is rules  # type: ignore[attr-defined]


def test_create_team_builder_defaults_to_bundled_team_master() -> None:
    """引数なしでは同梱のJSONチームマスタを使う。"""

    builder = create_team_builder()

    use_case = builder.build_team_plan
    assert isinstance(use_case, BuildTeamPlan)
    assert use_case.rules.team_master == load_default_team_master()


def test_default_rules_reads_given_team_master_path(tmp_path: Path) -> None:
    """パスを渡すと、同梱マスタの代わりにそのJSONを編成ルールへ使う。"""

    raw = json.loads(default_team_master_path().read_text(encoding="utf-8"))
    raw["member_cap"] = 10
    path = tmp_path / "team_master.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    rules = default_rules(path)

    assert rules.member_cap == 10
    assert rules.team_master != load_default_team_master()


def test_default_specification_reads_given_settings_path(tmp_path: Path) -> None:
    """パスを渡すと、同梱の例の代わりにそのsettings.jsonを運用者の指定に使う。"""

    path = tmp_path / "settings.json"
    _write_settings(path, [("ユウ", "AAA"), ("ミナ", "BBB"), ("ソラ", "AAA")])

    assert default_specification(path).leaders[0] == MemberRef("ユウ", "AAA")
    assert default_specification() == default_specification(default_settings_path())


def test_cli_uses_settings_and_team_master_given_by_option(
    tmp_path: Path,
    recording_builder: type[RecordingBuilder],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--settings`と`--team-master`で指定したファイルを使い、同梱の例の注意を出さない。"""

    settings_path = tmp_path / "settings.json"
    _write_settings(settings_path, [("ユウ", "AAA"), ("ミナ", "BBB"), ("ソラ", "AAA")])
    raw = json.loads(default_team_master_path().read_text(encoding="utf-8"))
    raw["member_cap"] = 10
    team_master_path = tmp_path / "本番のチームマスタ.json"
    team_master_path.write_text(json.dumps(raw), encoding="utf-8")

    exit_code = cli_main.main(
        [
            str(_input(tmp_path)),
            str(tmp_path / "出力.md"),
            "--team-master",
            str(team_master_path),
            "--settings",
            str(settings_path),
        ]
    )

    assert exit_code == 0
    assert [rules.member_cap for rules in recording_builder.rules] == [10]
    assert [spec.leaders[0].name for spec in recording_builder.specifications] == [
        "ユウ"
    ]
    assert (tmp_path / "出力.md").read_text(encoding="utf-8") == "出力\n"
    assert "同梱の例" not in capsys.readouterr().err


def test_cli_uses_bundled_examples_without_options(
    tmp_path: Path,
    recording_builder: type[RecordingBuilder],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--settings`を省略すると同梱の架空のリーダー一覧を使い、付け忘れに気づけるよう注意を出す。"""

    exit_code = cli_main.main([str(_input(tmp_path)), str(tmp_path / "出力.md")])

    assert exit_code == 0
    assert [rules.team_master for rules in recording_builder.rules] == [
        load_default_team_master()
    ]
    assert recording_builder.specifications == [default_specification()]
    error = capsys.readouterr().err
    assert "同梱の例（架空のリーダー一覧）で編成します" in error
    assert "--settings" in error


def test_cli_reports_team_master_load_error_with_exit_code_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """部品の組み立てから出た`TeamMasterLoadError`を、利用者向けの文言と終了コード2へ変換する。"""

    def broken_builder(rules: KvKRules) -> None:
        raise TeamMasterLoadError("チームマスタを読み込めません: 壊れたJSON")

    monkeypatch.setattr(cli_main, "create_team_builder", broken_builder)

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main([str(_input(tmp_path)), str(tmp_path / "出力.md")])

    assert exit_info.value.code == 2
    assert "エラー: チームマスタを読み込めません" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("option", "file_name", "message"),
    [
        ("--team-master", "存在しないマスタ.json", "チームマスタを読み込めません"),
        ("--settings", "存在しない指定.json", "運用者の指定を読み込めません"),
    ],
)
def test_cli_reports_missing_option_path_with_exit_code_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    option: str,
    file_name: str,
    message: str,
) -> None:
    """指定したファイルがなければ、パスを示して終了コード2で終え、出力を書かない。"""

    output_path = tmp_path / "出力.md"

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(
            [str(_input(tmp_path)), str(output_path), option, str(tmp_path / file_name)]
        )

    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert f"エラー: {message}" in error
    assert file_name in error
    assert not output_path.exists()


def test_cli_reports_leader_missing_from_roster_with_exit_code_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """リーダーが参加者一覧にいなければ、入力のエラーとして終了コード2で終える（FRM-047）。"""

    settings_path = tmp_path / "settings.json"
    _write_settings(
        settings_path, [("山田", "SKY"), ("いない人", "SKY"), ("いろは", "SKY")]
    )
    output_path = tmp_path / "出力.md"

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(
            [str(_input(tmp_path)), str(output_path), "--settings", str(settings_path)]
        )

    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert (
        "エラー: リーダー一覧の2番目（第2隊のリーダー）が、名前と同盟の組で参加者一覧に見つかりません"
        in error
    )
    assert "いない人" not in error
    assert not output_path.exists()


def test_module_entry_point_shows_usage() -> None:
    """READMEが案内する`python -m kvk_team.interfaces.cli`で起動できる。"""

    environment = {
        **os.environ,
        "PYTHONPATH": str(SOURCE_ROOT),
        "PYTHONIOENCODING": "utf-8",
    }
    result = subprocess.run(
        [sys.executable, "-m", "kvk_team.interfaces.cli", "--help"],
        capture_output=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "参加者一覧Markdownのパス" in result.stdout
    assert "--team-master" in result.stdout
    assert "--settings" in result.stdout


def test_console_script_resolves_to_cli_main() -> None:
    """`kvk-team-builder`の参照先がCLIのmain関数を指す。"""

    target = _pyproject()["project"]["scripts"]["kvk-team-builder"]
    module_name, function_name = target.split(":")

    assert getattr(importlib.import_module(module_name), function_name) is cli_main.main


def test_package_data_points_to_existing_files() -> None:
    """package-dataの各キーが実在するパッケージとファイルを指し、同梱の例と一致する。"""

    package_data = _pyproject()["tool"]["setuptools"]["package-data"]
    files = [
        SOURCE_ROOT.joinpath(*package.split("."), name)
        for package, names in package_data.items()
        for name in names
    ]

    assert files
    assert all(path.is_file() for path in files), files
    resolved = {path.resolve() for path in files}
    assert default_team_master_path().resolve() in resolved
    assert default_settings_path().resolve() in resolved


def _fail_with(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    class FailingBuilder:
        def __init__(self, rules: KvKRules) -> None:
            pass

        def build(
            self,
            markdown: str,
            specification: OperatorSpecification,
            answers: tuple[Answer, ...] = (),
        ) -> str:
            raise error

    monkeypatch.setattr(cli_main, "create_team_builder", FailingBuilder)


SHORTFALL = LowerBoundShortfallError(
    [
        ValidationIssue(
            ValidationCode.REST,
            "第4隊は所属メンバーが参加しておらず休止になります",
            4,
            TimeSlot(21 * 60, 21 * 60 + 30),
        )
    ],
    [ShortfallQuestion(1, 4, (TimeSlot(21 * 60, 21 * 60 + 30),), opening=True)],
    ["第5隊 21:00への回答（第6隊を22:00から出撃）は使いませんでした"],
)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (BuildError("3回の再配置後も検証NGです: 人数NG"), 2),
        (NoValidPlanError("上位隊の人数を満たす編成は存在しません"), 2),
        (OptimizationTimeoutError("時間切れのため、編成の有無は未確定です"), 4),
        (ShortfallUndeterminedError("時間切れのため、確定できません"), 4),
    ],
)
def test_cli_reports_errors_with_exit_code_and_writes_no_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    code: int,
) -> None:
    """出力できない場合は出力を書かずに理由を示し、入力のエラーと解なしは2、時間切れは4で終える。"""

    output_path = tmp_path / "出力.md"
    _fail_with(monkeypatch, error)

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main([str(_input(tmp_path)), str(output_path)])

    assert exit_info.value.code == code
    assert f"エラー: {error}" in capsys.readouterr().err
    assert not output_path.exists()


def test_cli_shows_numbered_questions_with_exit_code_3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """運用者の判断が要る場合は、番号付きの質問と注記を示し、出力を書かずに3で終える（FRM-075）。"""

    output_path = tmp_path / "出力.md"
    _fail_with(monkeypatch, SHORTFALL)

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main([str(_input(tmp_path)), str(output_path)])

    error = capsys.readouterr().err
    assert exit_info.value.code == 3
    assert "問1: 第4隊 21:00（序盤）" in error
    assert "注記: 第5隊 21:00への回答" in error
    assert not output_path.exists()


def _write_answers(path: Path, raw: object) -> Path:
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


def test_cli_passes_answers_file_to_builder(
    tmp_path: Path, recording_builder: type[RecordingBuilder]
) -> None:
    """--answersで渡した回答を読み、編成へ渡す（DAT-009）。"""

    answers_path = _write_answers(
        tmp_path / "answers.json",
        {
            "answers": [
                {
                    "target": {"team": 7, "time": "21:00"},
                    "late_start": {"team": 10, "start": "22:00"},
                }
            ]
        },
    )
    arguments = [str(_input(tmp_path)), str(tmp_path / "出力.md")]

    exit_code = cli_main.main([*arguments, "--answers", str(answers_path)])

    assert exit_code == 0
    assert len(recording_builder.answers[-1]) == 1
    assert recording_builder.answers[-1][0].late_start.team == 10


def test_cli_without_answers_passes_no_answers(
    tmp_path: Path, recording_builder: type[RecordingBuilder]
) -> None:
    """--answersを省略すれば、回答なしで編成する。"""

    cli_main.main([str(_input(tmp_path)), str(tmp_path / "出力.md")])

    assert recording_builder.answers[-1] == ()


def test_cli_reports_answers_load_error_with_exit_code_2(
    tmp_path: Path,
    recording_builder: type[RecordingBuilder],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """回答のファイルを読めなければ、パスを示して終了コード2で終える。"""

    answers_path = _write_answers(
        tmp_path / "answers.json", {"answers": [{"number": 1}]}
    )
    output_path = tmp_path / "出力.md"
    arguments = [str(_input(tmp_path)), str(output_path)]

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main([*arguments, "--answers", str(answers_path)])

    assert exit_info.value.code == 2
    assert "answers.json" in capsys.readouterr().err
    assert not output_path.exists()
