"""CP-SATを実行するテストで共有する、再現可能なルール設定。"""

from dataclasses import replace

from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.team_building.domain.rules import KvKRules

DETERMINISTIC_TIME_LIMIT = 1.0
"""最初の実行可能解に十分な余裕を持つ決定的時間。"""

WALL_CLOCK_GUARD_SECONDS = 120.0
"""決定的時間より先に到達しないよう、停止しない場合だけを防ぐ実時間の上限。"""


def deterministic_rules(
    deterministic_time: float = DETERMINISTIC_TIME_LIMIT,
) -> KvKRules:
    """実行環境の速さや負荷に依存しない探索結果を返すルールを生成する。

    並列探索は実時間に依存してworker間の結果共有が変わるため、1 workerに固定し、
    実時間ではなく決定的時間で探索を打ち切る。
    """

    return replace(
        default_rules(),
        maximum_optimization_seconds=WALL_CLOCK_GUARD_SECONDS,
        maximum_deterministic_time=deterministic_time,
        solver_worker_count=1,
    )
