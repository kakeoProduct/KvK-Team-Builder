"""運用形式の参加者一覧からMarkdownを生成するフローの統合テスト。"""

from pathlib import Path

from deterministic_solver import deterministic_rules
from kvk_team.interfaces.cli.composition import (
    create_team_builder,
    default_specification,
)
from kvk_team.team_building.adapters.input.markdown_member_parser import (
    MarkdownMemberParser,
)
from kvk_team.team_building.domain.specification import resolve_leaders

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROSTER = PROJECT_ROOT / "sample" / "参加者一覧.md"


def test_sample_roster_contains_every_bundled_leader() -> None:
    """同梱の例のリーダーが全員、名前と同盟の組でサンプルにいる。

    片方だけを変えると、サンプルの編成が入力のエラーで止まるため。
    """

    members = MarkdownMemberParser().parse(SAMPLE_ROSTER.read_text(encoding="utf-8"))

    leaders = resolve_leaders(default_specification(), members)

    assert len(leaders) == 11


def test_sample_roster_builds_valid_markdown() -> None:
    """管理対象の運用形式のサンプルがパイプライン全体を通過する。"""

    source = SAMPLE_ROSTER.read_text(encoding="utf-8")

    markdown = create_team_builder(deterministic_rules()).build(
        source, default_specification()
    )

    assert "## 第1隊 リーダー: 山田" in markdown
    assert "## 第11隊 リーダー: 翡翠" in markdown
    assert "## 【別枠】参加時間未定 1人" in markdown
    assert "## 時間帯別の出撃" in markdown
    assert "- 必須条件: OK" in markdown
    assert "NG" not in markdown
