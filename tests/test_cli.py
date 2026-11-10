"""CLIのファイル処理テスト。"""

from pathlib import Path

from kvk_team.interfaces.cli import main as cli_main
from kvk_team.team_building.domain.specification import OperatorSpecification


def test_cli_reads_and_writes_utf8_markdown(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """UTF-8入力をサービスへ渡し、その結果をファイルへ出力する。"""

    input_path = tmp_path / "参加者一覧.md"
    output_path = tmp_path / "チーム編成.md"
    input_path.write_text("同盟名:SKY\nG8:\n山田◯◇\n", encoding="utf-8")

    def fake_build(
        self, source: str, specification: OperatorSpecification, answers: tuple = ()
    ) -> str:
        assert "山田" in source
        assert specification.team_count == 11
        return "## 第1隊 リーダー: 山田\n"

    monkeypatch.setattr(cli_main.TeamBuilder, "build", fake_build)

    exit_code = cli_main.main([str(input_path), str(output_path)])

    assert exit_code == 0
    assert output_path.read_text(encoding="utf-8") == "## 第1隊 リーダー: 山田\n"
