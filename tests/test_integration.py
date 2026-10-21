"""運用形式の参加者一覧からMarkdownを生成するフローの統合テスト。"""

from pathlib import Path

from deterministic_solver import deterministic_rules
from kvk_team.interfaces.cli.composition import create_team_builder
from kvk_team.team_building.adapters.input.markdown_member_parser import (
    MarkdownMemberParser,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROSTER = PROJECT_ROOT / "sample" / "参加者一覧.md"


def test_sample_roster_contains_every_bundled_rally_leader() -> None:
    """同梱の例の固定集結主が全員サンプルにいる。名前を片方だけ変えると到着待ちの警告で隠れるため。"""

    members = MarkdownMemberParser().parse(SAMPLE_ROSTER.read_text(encoding="utf-8"))
    names = {member.name for member in members}

    missing = set(deterministic_rules().rally_leaders.values()) - names

    assert missing == set()


def test_sample_roster_builds_valid_markdown() -> None:
    """管理対象の運用形式のサンプルがパイプライン全体を通過する。"""

    source = SAMPLE_ROSTER.read_text(encoding="utf-8")
    rules = deterministic_rules()

    markdown = create_team_builder(rules).build(source)

    assert all(f"## {label}（" in markdown for label in "ABCDEFGHIJK")
    assert "## 時間帯別チーム集計" in markdown
    assert "## 自己チェック" in markdown
    assert "NG" not in markdown
