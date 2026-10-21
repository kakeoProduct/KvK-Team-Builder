"""Optimizer共通の例外。"""


class OptimizationError(RuntimeError):
    """参加者集合から必須ルールを満たす編成を出力できない場合に送出する。"""


class InfeasibleRosterError(OptimizationError):
    """必須ルールを満たす編成が存在しないとSolverが証明した場合に送出する。"""


class OptimizationTimeoutError(OptimizationError):
    """編成の有無を確定する前に探索の制限へ達した場合に送出する。"""
