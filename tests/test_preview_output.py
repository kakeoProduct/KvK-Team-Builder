"""生成結果を運用者視点で確認する補助Scriptのテスト。"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from kvk_team.team_building.application.build_team_plan import BuildError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREVIEW_SCRIPT = PROJECT_ROOT / "tools" / "preview_output.py"

PREVIOUS_MARKDOWN = """## A（役割A）（最大8）

### 21:00 初期配置

山田
SKY01

## 自己チェック

- 必須条件: OK
- 時間確定待ち: 0人
- 警告: 1件

### 警告詳細

- 21:00: Jが8人未満です: 3人
"""

CURRENT_MARKDOWN = """## A（役割A）（最大8）

### 21:00 初期配置

山田
SKY02

## 自己チェック

- 必須条件: OK
- 時間確定待ち: 1人
- 警告: 2件

### 警告詳細

- 21:00: Jが8人未満です: 3人
- 21:00: Kが8人未満です: 1人
"""


def _load_preview_module() -> ModuleType:
    """確認Scriptをモジュールとして読み込む。"""

    spec = importlib.util.spec_from_file_location("preview_output", PREVIEW_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_summary_shows_self_check_and_warnings() -> None:
    """要約は自己チェックと警告詳細を運用者が読める形で残す。"""

    module = _load_preview_module()

    summary = module.summarize(CURRENT_MARKDOWN)

    assert "- 必須条件: OK" in summary
    assert "- 時間確定待ち: 1人" in summary
    assert "- 21:00: Kが8人未満です: 1人" in summary
    assert "SKY02" not in summary


def test_compare_reports_only_changed_lines() -> None:
    """前回出力との比較は変化した配置と警告だけを示す。"""

    module = _load_preview_module()

    difference = module.compare(PREVIOUS_MARKDOWN, CURRENT_MARKDOWN)

    assert "-SKY01" in difference
    assert "+SKY02" in difference
    assert "+- 21:00: Kが8人未満です: 1人" in difference
    assert "山田" not in difference
    assert module.compare(CURRENT_MARKDOWN, CURRENT_MARKDOWN) == ""


def test_main_keeps_previous_output_and_prints_difference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """再実行時は前回出力を退避し、要約と差分を表示する。"""

    module = _load_preview_module()
    roster = tmp_path / "参加者一覧.md"
    roster.write_text("参加者\n", encoding="utf-8")
    output = tmp_path / "preview" / "チーム編成.md"
    outputs = iter((PREVIOUS_MARKDOWN, CURRENT_MARKDOWN))
    received: list[str] = []

    def build(source: str) -> str:
        received.append(source)
        return next(outputs)

    arguments = ["--input", str(roster), "--output", str(output)]
    assert module.main(arguments, build=build) == 0
    first = capsys.readouterr().out
    assert "前回の出力がないため差分はありません" in first

    assert module.main(arguments, build=build) == 0
    second = capsys.readouterr().out

    assert received == ["参加者\n", "参加者\n"]
    assert output.read_text(encoding="utf-8") == CURRENT_MARKDOWN
    previous = output.with_name("チーム編成.previous.md")
    assert previous.read_text(encoding="utf-8") == PREVIOUS_MARKDOWN
    assert "- 警告: 2件" in second
    assert "+SKY02" in second


def test_main_reports_build_error_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """必須条件エラーは出力ファイルを作らず、非0で終了する。"""

    module = _load_preview_module()
    roster = tmp_path / "参加者一覧.md"
    roster.write_text("参加者\n", encoding="utf-8")
    output = tmp_path / "チーム編成.md"

    def build(_source: str) -> str:
        raise BuildError("必須条件を満たす編成がありません")

    status = module.main(["--input", str(roster), "--output", str(output)], build=build)

    assert status == 2
    assert not output.exists()
    assert "必須条件を満たす編成がありません" in capsys.readouterr().err
