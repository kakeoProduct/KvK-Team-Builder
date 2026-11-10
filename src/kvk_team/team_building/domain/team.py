"""隊の番号と、運用で変えない固定値（ADR 0034）。

隊の数はリーダーの人数で決まり、リーダー一覧の番号が隊の番号になる（FRM-001）。
上位隊の数と人数、延長境界時刻、出撃人数の下限の基本、30分単位の時間帯は利用者が決めた
固定値であり、運用値（チームマスタ、運用者の指定）ではなくドメインの定数として持つ。
戦力関係は固定値ではなく、分割案の3でFRM-027へ置き換えるまで維持する現行の規則である。
"""

from kvk_team.team_building.domain.member import MINUTES_PER_HOUR

SLOT_MINUTES = 30
"""時間帯の長さ（分）。利用者が決めた固定値で、設定では変えない。"""

TOP_TEAM_COUNT = 3
"""上位隊（第1〜3隊）の数。固定をなくさない（FRM-026）。"""

TOP_TEAM_SIZE = 8
"""上位隊のリーダーを含む人数（FRM-020）。リーダー不在の時間帯は1人少ない。"""

SORTIE_FLOOR = 8
"""出撃人数の下限の基本（FRM-031）。第4隊以降で下回ると警告にする。"""

EXTENSION_BOUNDARY_MINUTES = 24 * MINUTES_PER_HOUR
"""延長境界時刻（FRM-043）。これより前の休止は下限の不足として扱う（FRM-048）。"""

STRICTLY_STRONGER_PAIRS = ((1, 2),)
"""戦力で「>」を満たす上位隊の組（以前の`A > B`）。分割案の3まで維持する現行の規則で、
FRM-027の平均Gの比較へ置き換える。"""

AT_LEAST_AS_STRONG_PAIRS = ((2, 3),)
"""戦力で「>=」を満たす上位隊の組（現行の`B >= C`）。"""


def is_top_team(number: int) -> bool:
    """隊の番号が上位隊かを返す。"""

    return 1 <= number <= TOP_TEAM_COUNT


def team_name(number: int) -> str:
    """隊の番号を運用者向けの名前にする。"""

    return f"第{number}隊"
