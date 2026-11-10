"""Optimizer共通の例外。

解がないことの証明は例外にせず、`application.ports.ProvenInfeasible`として返す（ADR 0034）。
"""

from kvk_team.team_building.application.ports import SearchTimeoutError


class OptimizationError(RuntimeError):
    """参加者集合から必須ルールを満たす編成を出力できない場合に送出する。"""


class OptimizationTimeoutError(OptimizationError, SearchTimeoutError):
    """編成の有無を確定する前に探索の制限へ達した場合に送出する（時間切れの共通の型。ADR 0035）。"""
