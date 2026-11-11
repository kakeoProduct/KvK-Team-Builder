"""CLIのファイル処理テスト。出力のフォルダの`<実行の時刻>/`へ編成のMarkdownとJSONを書く（DAT-008、ADR 0036）。"""

import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from kvk_team.interfaces.cli import main as cli_main
from kvk_team.interfaces.cli import run_output
from kvk_team.interfaces.cli.team_builder import TeamBuildResult
from kvk_team.team_building.adapters.persistence.json_plan_record_repository import (
    render_plan_record,
)
from kvk_team.team_building.domain.answers import Answer
from kvk_team.team_building.domain.plan_record import PlanRecord, RecordedTeam
from kvk_team.team_building.domain.specification import (
    MemberRef,
    OperatorSpecification,
)

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 1, 1, 21, 52, 30, tzinfo=JST)
YAMADA = MemberRef("山田", "SKY")
RECORD = PlanRecord(
    created_at=NOW,
    teams=(RecordedTeam(1, YAMADA, (YAMADA,)),),
)


class FakeBuilder:
    """buildに渡した値を記録し、固定の結果を返す。"""

    specifications: list[OperatorSpecification] = []
    created_at: list[datetime] = []
    unmatched: int | None = None

    def __init__(self, rules: object) -> None:
        pass

    def build(
        self,
        markdown: str,
        specification: OperatorSpecification,
        answers: tuple[Answer, ...] = (),
        *,
        created_at: datetime,
    ) -> TeamBuildResult:
        assert "山田" in markdown
        FakeBuilder.specifications.append(specification)
        FakeBuilder.created_at.append(created_at)
        return TeamBuildResult(
            markdown="## 第1隊 リーダー: 山田\n",
            record=RECORD,
            previous_unmatched=(
                None if specification.previous_plan is None else FakeBuilder.unmatched
            ),
        )


@pytest.fixture
def fake_builder(monkeypatch: pytest.MonkeyPatch) -> type[FakeBuilder]:
    FakeBuilder.specifications = []
    FakeBuilder.created_at = []
    FakeBuilder.unmatched = 0
    monkeypatch.setattr(cli_main, "create_team_builder", FakeBuilder)
    return FakeBuilder


def _input(tmp_path: Path) -> Path:
    path = tmp_path / "参加者一覧.md"
    path.write_text("同盟名:SKY\nG8:\n山田◯◇\n", encoding="utf-8")
    return path


def _run(tmp_path: Path, *extra: str) -> int:
    arguments = [str(_input(tmp_path)), str(tmp_path / "output"), *extra]
    try:
        return cli_main.main(arguments, clock=lambda: NOW)
    except SystemExit as exit_info:
        return int(exit_info.code or 0)


def test_cli_writes_markdown_and_json_into_folder_named_by_run_time(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """出力のフォルダの`YYYYMMDD-HHMMSS`のフォルダへ、編成のMarkdownとJSONをUTF-8で書く。"""

    assert _run(tmp_path) == 0

    folder = tmp_path / "output" / "20260101-215230"
    assert (folder / "チーム編成.md").read_text(encoding="utf-8") == (
        "## 第1隊 リーダー: 山田\n"
    )
    assert (folder / "チーム編成.json").read_text(
        encoding="utf-8"
    ) == render_plan_record(RECORD)
    assert fake_builder.created_at == [NOW]
    assert str(folder) in capsys.readouterr().out


def test_cli_does_not_overwrite_folder_of_same_time(
    tmp_path: Path, fake_builder: type[FakeBuilder]
) -> None:
    """同じ時刻のフォルダがあれば`-2`、`-3`を付け、前の出力を上書きしない。"""

    existing = tmp_path / "output" / "20260101-215230"
    existing.mkdir(parents=True)
    (existing / "チーム編成.md").write_text("共有した回\n", encoding="utf-8")

    assert _run(tmp_path) == 0
    assert _run(tmp_path) == 0

    assert (existing / "チーム編成.md").read_text(encoding="utf-8") == "共有した回\n"
    assert not (existing / "チーム編成.json").exists()
    for name in ("20260101-215230-2", "20260101-215230-3"):
        assert (tmp_path / "output" / name / "チーム編成.json").is_file()


@pytest.mark.parametrize(
    ("name", "previous_output"),
    [
        ("チーム編成.md", None),
        ("チーム編成.MD", None),
        ("チーム編成.md", "以前の版の出力\n"),
    ],
)
def test_cli_rejects_markdown_output_path_with_exit_code_2(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    capsys: pytest.CaptureFixture[str],
    name: str,
    previous_output: str | None,
) -> None:
    """以前の書き方（出力Markdownのパス）は、大文字の拡張子も、置き方が変わったことを示して入力のエラーにする。"""

    output = tmp_path / name
    if previous_output is not None:
        output.write_text(previous_output, encoding="utf-8")
    arguments = [str(_input(tmp_path)), str(output)]

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(arguments, clock=lambda: NOW)

    assert exit_info.value.code == 2
    error = capsys.readouterr().err
    assert "出力のフォルダ" in error
    assert "<実行の時刻>" in error
    if previous_output is None:
        assert not output.exists()
    else:
        assert output.read_text(encoding="utf-8") == previous_output
    assert fake_builder.specifications == []


def test_cli_reports_output_folder_that_is_a_file_with_exit_code_2(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """出力のフォルダがファイルなら、編成の前にパスを示して終了コード2で終え、ファイルを変えない。"""

    (tmp_path / "output").write_text("前の内容", encoding="utf-8")

    assert _run(tmp_path) == 2
    error = capsys.readouterr().err
    assert "出力のフォルダがフォルダではありません" in error
    assert str(tmp_path / "output") in error
    assert fake_builder.specifications == []
    assert (tmp_path / "output").read_text(encoding="utf-8") == "前の内容"


def test_cli_reads_clock_once_for_folder_name_and_created_at(
    tmp_path: Path, fake_builder: type[FakeBuilder]
) -> None:
    """フォルダ名と編成の記録の時刻は、1回だけ読んだ同じ時刻から作る（作成者の仮定A-42の(5)）。"""

    readings = [NOW.replace(microsecond=123456), NOW + timedelta(minutes=5)]
    calls: list[datetime] = []

    def advancing_clock() -> datetime:
        calls.append(readings[len(calls)])
        return calls[-1]

    arguments = [str(_input(tmp_path)), str(tmp_path / "output")]
    assert cli_main.main(arguments, clock=advancing_clock) == 0

    assert calls == [readings[0]]
    assert fake_builder.created_at == [readings[0]]
    assert [folder.name for folder in (tmp_path / "output").iterdir()] == [
        "20260101-215230"
    ]


def test_cli_exits_0_when_stdout_cannot_encode_japanese(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """標準出力の符号化が日本語を表せなくても（Windowsのリダイレクト）、書いた回を終了コード0で終える。"""

    buffer = io.BytesIO()
    stdout = io.TextIOWrapper(buffer, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stdout)

    assert _run(tmp_path) == 0

    stdout.flush()
    assert b"20260101-215230" in buffer.getvalue()


def test_cli_gives_up_after_too_many_folders_of_same_time(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """同じ時刻のフォルダの番号を使い切ったら、前の出力を変えずに終了コード2で終える。"""

    monkeypatch.setattr(run_output, "MAXIMUM_SUFFIX", 2)
    assert _run(tmp_path) == 0
    assert _run(tmp_path) == 0
    capsys.readouterr()

    assert _run(tmp_path) == 2

    assert "同じ時刻の出力のフォルダが多すぎます" in capsys.readouterr().err
    assert sorted(folder.name for folder in (tmp_path / "output").iterdir()) == [
        "20260101-215230",
        "20260101-215230-2",
    ]


@pytest.mark.parametrize("failing_suffix", [".md", ".json"])
def test_cli_removes_partly_written_folder_with_exit_code_2(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failing_suffix: str,
) -> None:
    """MarkdownかJSONを書けなければ、片方だけのフォルダを残さずに、書けなかった理由を示して2で終える。"""

    original = Path.write_text

    def failing_write_text(self: Path, *args: object, **kwargs: object) -> int:
        if self.suffix == failing_suffix and "output" in self.parts:
            raise OSError("ディスクがいっぱいです")
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", failing_write_text)

    assert _run(tmp_path) == 2
    assert list((tmp_path / "output").iterdir()) == []
    assert "ディスクがいっぱいです" in capsys.readouterr().err


def test_cli_reports_write_error_even_if_cleanup_fails(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """後始末にも失敗した場合も、後始末の失敗で書けなかった理由を隠さない。"""

    original = Path.write_text

    def failing_write_text(self: Path, *args: object, **kwargs: object) -> int:
        if self.suffix == ".json":
            raise OSError("ディスクがいっぱいです")
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    def failing_rmdir(self: Path) -> None:
        raise OSError("ほかのプロセスが使用中です")

    monkeypatch.setattr(Path, "write_text", failing_write_text)
    monkeypatch.setattr(Path, "rmdir", failing_rmdir)

    assert _run(tmp_path) == 2
    error = capsys.readouterr().err
    assert "ディスクがいっぱいです" in error
    assert "ほかのプロセスが使用中です" not in error
    assert "途中まで書いたフォルダを消せませんでした" in error
    assert str(tmp_path / "output" / "20260101-215230") in error


def test_cli_reports_output_folder_that_cannot_be_checked_with_exit_code_2(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """出力のフォルダを確かめられなければ（親を辿れないなど）、編成の前に終了コード2で終える。"""

    original = Path.exists

    def failing_exists(self: Path, *args: object, **kwargs: object) -> bool:
        if self.name == "output":
            raise PermissionError("許可がありません")
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "exists", failing_exists)

    assert _run(tmp_path) == 2
    assert "出力のフォルダを確かめられません" in capsys.readouterr().err
    assert fake_builder.specifications == []


def test_default_clock_has_local_offset() -> None:
    """既定の時計は現地時刻を時差付きで返す（DAT-002）。"""

    assert cli_main.local_now().utcoffset() is not None


def _write_previous(tmp_path: Path, raw: object) -> Path:
    path = tmp_path / "前回.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


def test_cli_passes_previous_plan_and_says_it_is_not_used_yet(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--previousの編成のJSONを運用者の指定に持たせ、この版では編成に使わないと注意を出す。"""

    previous = tmp_path / "前回.json"
    previous.write_text(render_plan_record(RECORD), encoding="utf-8")

    assert _run(tmp_path, "--previous", str(previous)) == 0

    assert [spec.previous_plan for spec in fake_builder.specifications] == [RECORD]
    error = capsys.readouterr().err
    assert "この版では" in error
    assert "編成には使いません" in error
    assert "参加者一覧にいません" not in error


def test_cli_reports_unmatched_previous_members_by_count_only(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """前回の編成のうち今回の参加者一覧にいない人数を、名前を書かずに示す。"""

    previous = tmp_path / "前回.json"
    previous.write_text(render_plan_record(RECORD), encoding="utf-8")
    fake_builder.unmatched = 2

    assert _run(tmp_path, "--previous", str(previous)) == 0

    error = capsys.readouterr().err
    assert "前回の編成の2人が、今回の参加者一覧（名前と同盟の組）にいません" in error


def test_cli_without_previous_has_no_previous_plan_or_notice(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--previousを省略すれば前回の編成なしで編成し、前回の編成の注意を出さない。"""

    assert _run(tmp_path) == 0

    assert fake_builder.specifications[0].previous_plan is None
    assert "前回の編成" not in capsys.readouterr().err


def test_cli_reports_previous_load_error_with_exit_code_2_and_writes_nothing(
    tmp_path: Path,
    fake_builder: type[FakeBuilder],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """前回の編成を読めなければ、パスを示して終了コード2で終え、出力のフォルダを作らない。"""

    previous = _write_previous(tmp_path, {"schema_version": 1, "teams": []})

    assert _run(tmp_path, "--previous", str(previous)) == 2

    assert "前回の編成を読み込めません" in capsys.readouterr().err
    assert not (tmp_path / "output").exists()
    assert fake_builder.specifications == []
