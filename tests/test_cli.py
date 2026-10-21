"""CLIのファイル処理テスト。"""

from pathlib import Path

from kvk_team.interfaces.cli import main as cli_main


def test_cli_reads_and_writes_utf8_markdown(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """UTF-8入力をサービスへ渡し、その結果をファイルへ出力する。"""

    input_path = tmp_path / "参加者一覧.md"
    output_path = tmp_path / "チーム編成.md"
    input_path.write_text("同盟名:SKY\nG8:\n山田◯◇\n", encoding="utf-8")

    def fake_build(self, source: str) -> str:
        assert "山田" in source
        return "## A（7）\n"

    monkeypatch.setattr(cli_main.TeamBuilder, "build", fake_build)

    exit_code = cli_main.main([str(input_path), str(output_path)])

    assert exit_code == 0
    assert output_path.read_text(encoding="utf-8") == "## A（7）\n"
