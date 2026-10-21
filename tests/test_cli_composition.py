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
from kvk_team.interfaces.cli.composition import create_team_builder, default_rules
from kvk_team.team_building.adapters.persistence.json_team_master_repository import (  # noqa: E501
    TeamMasterLoadError,
    default_team_master_path,
    load_default_team_master,
)
from kvk_team.team_building.application.build_team_plan import (
    BuildError,
    BuildTeamPlan,
)
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.team import TeamLabel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"


def _pyproject() -> dict:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as source:
        return tomllib.load(source)


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


def test_cli_reports_team_master_load_error_with_exit_code_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """部品の組み立てから出た`TeamMasterLoadError`を、利用者向けの文言と終了コード2へ変換する。

    実際のファイルの読み込み失敗は`test_cli_reports_missing_team_master_option_path_with_exit_code_2`
    が確かめる。
    """

    input_path = tmp_path / "参加者一覧.md"
    input_path.write_text("同盟名:SKY\nG8:山田◯◇\n", encoding="utf-8")

    def broken_builder(rules: KvKRules) -> None:
        raise TeamMasterLoadError("チームマスタを読み込めません: 壊れたJSON")

    monkeypatch.setattr(cli_main, "create_team_builder", broken_builder)

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main([str(input_path), str(tmp_path / "出力.md")])

    assert exit_info.value.code == 2
    assert "エラー: チームマスタを読み込めません" in capsys.readouterr().err


def _write_team_master_with_leader(path: Path, leader: str) -> None:
    """同梱マスタのAの集結主だけを変えたJSONを書く。"""

    raw = json.loads(default_team_master_path().read_text(encoding="utf-8"))
    raw["teams"][0]["rally_leader"] = leader
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")


def test_default_rules_reads_given_team_master_path(tmp_path: Path) -> None:
    """パスを渡すと、同梱マスタの代わりにそのJSONを編成ルールへ使う。"""

    team_master_path = tmp_path / "team_master.json"
    _write_team_master_with_leader(team_master_path, "指定した集結主")

    rules = default_rules(team_master_path)

    assert rules.rally_leaders[TeamLabel.A] == "指定した集結主"
    assert rules.team_master != load_default_team_master()


def test_cli_uses_team_master_given_by_option(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--team-master`で指定したJSONの編成ルールでTeamBuilderを組み立てる。"""

    input_path = tmp_path / "参加者一覧.md"
    input_path.write_text("同盟名:SKY\nG8:山田◯◇\n", encoding="utf-8")
    team_master_path = tmp_path / "本番のチームマスタ.json"
    _write_team_master_with_leader(team_master_path, "指定した集結主")
    received: list[KvKRules] = []

    class RecordingBuilder:
        def __init__(self, rules: KvKRules) -> None:
            received.append(rules)

        def build(self, markdown: str) -> str:
            return "出力\n"

    monkeypatch.setattr(cli_main, "create_team_builder", RecordingBuilder)

    exit_code = cli_main.main(
        [
            str(input_path),
            str(tmp_path / "出力.md"),
            "--team-master",
            str(team_master_path),
        ]
    )

    assert exit_code == 0
    assert [rules.rally_leaders[TeamLabel.A] for rules in received] == [
        "指定した集結主"
    ]
    assert (tmp_path / "出力.md").read_text(encoding="utf-8") == "出力\n"
    assert "同梱の例" not in capsys.readouterr().err


def test_cli_uses_bundled_team_master_without_option(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--team-master`を省略すると同梱の例を使い、付け忘れに気づけるよう標準エラーへ注意を出す。"""

    input_path = tmp_path / "参加者一覧.md"
    input_path.write_text("同盟名:SKY\nG8:山田◯◇\n", encoding="utf-8")
    received: list[KvKRules] = []

    class RecordingBuilder:
        def __init__(self, rules: KvKRules) -> None:
            received.append(rules)

        def build(self, markdown: str) -> str:
            return "出力\n"

    monkeypatch.setattr(cli_main, "create_team_builder", RecordingBuilder)

    exit_code = cli_main.main([str(input_path), str(tmp_path / "出力.md")])

    assert exit_code == 0
    assert [rules.team_master for rules in received] == [load_default_team_master()]
    error = capsys.readouterr().err
    assert "同梱の例（架空の集結主と役割）で編成します" in error
    assert "--team-master" in error


def test_cli_reports_missing_team_master_option_path_with_exit_code_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--team-master`のファイルがなければ、パスを示して終了コード2で終え、出力を書かない。"""

    input_path = tmp_path / "参加者一覧.md"
    input_path.write_text("同盟名:SKY\nG8:山田◯◇\n", encoding="utf-8")
    output_path = tmp_path / "出力.md"
    missing_path = tmp_path / "存在しないマスタ.json"

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(
            [str(input_path), str(output_path), "--team-master", str(missing_path)]
        )

    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert "エラー: チームマスタを読み込めません" in error
    assert "存在しないマスタ.json" in error
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


def test_console_script_resolves_to_cli_main() -> None:
    """`kvk-team-builder`の参照先がCLIのmain関数を指す。"""

    target = _pyproject()["project"]["scripts"]["kvk-team-builder"]
    module_name, function_name = target.split(":")

    assert getattr(importlib.import_module(module_name), function_name) is cli_main.main


def test_package_data_points_to_existing_files() -> None:
    """package-dataの各キーが実在するパッケージとファイルを指し、既定マスタと一致する。"""

    package_data = _pyproject()["tool"]["setuptools"]["package-data"]
    files = [
        SOURCE_ROOT.joinpath(*package.split("."), name)
        for package, names in package_data.items()
        for name in names
    ]

    assert files
    assert all(path.is_file() for path in files), files
    assert default_team_master_path().resolve() in {path.resolve() for path in files}


def test_cli_reports_build_error_with_exit_code_2_and_writes_no_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """再試行の上限に達したら、出力ファイルを書かずに終了コード2で終える。"""

    input_path = tmp_path / "参加者一覧.md"
    output_path = tmp_path / "出力.md"
    input_path.write_text("同盟名:SKY\nG8:山田◯◇\n", encoding="utf-8")

    class FailingBuilder:
        def __init__(self, rules: KvKRules) -> None:
            pass

        def build(self, markdown: str) -> str:
            raise BuildError("3回の再配置後も検証NGです: 人数NG")

    monkeypatch.setattr(cli_main, "create_team_builder", FailingBuilder)

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main([str(input_path), str(output_path)])

    assert exit_info.value.code == 2
    assert "エラー: 3回の再配置後も検証NGです" in capsys.readouterr().err
    assert not output_path.exists()
