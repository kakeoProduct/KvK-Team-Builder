"""テスト全体で共有するHypothesisの設定。"""

from hypothesis import settings

HYPOTHESIS_PROFILE = "kvk-deterministic"

# 手元とCIで同じ入力を生成し、実行時間や前回の失敗例で結果が変わらないようにする（ADR 0025）。
# CI上で自動的に読み込まれる`ci` Profileの値を引き継がないよう、組み込みの既定値を親にする。
settings.register_profile(
    HYPOTHESIS_PROFILE,
    parent=settings.get_profile("default"),
    derandomize=True,
    database=None,
    deadline=None,
    print_blob=True,
)
settings.load_profile(HYPOTHESIS_PROFILE)
