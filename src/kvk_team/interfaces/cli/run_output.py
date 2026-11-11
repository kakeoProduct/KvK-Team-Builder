"""1回の実行の出力を、出力のフォルダの`<実行の時刻>/`へ上書きせずに書く（DAT-008、ADR 0036）。

運用者は共有した回のフォルダの編成のJSONを、次の実行へ`--previous`で渡す。前の回の出力を失わない
よう、同じ名前のフォルダがあれば`-2`、`-3`を付けた新しいフォルダへ書く。
"""

import contextlib
from datetime import datetime
from pathlib import Path

MARKDOWN_NAME = "チーム編成.md"
"""編成のMarkdownのファイル名。"""
PLAN_JSON_NAME = "チーム編成.json"
"""編成のJSON（DAT-010）のファイル名。"""
FOLDER_TIME_FORMAT = "%Y%m%d-%H%M%S"
"""フォルダ名の時刻の形。Windowsで使えない`:`を含めない。"""
MAXIMUM_SUFFIX = 999
"""同じ時刻のフォルダに付ける番号の上限。"""


def run_folder_name(created_at: datetime, number: int = 1) -> str:
    """実行の時刻のフォルダ名を返す。2つ目以降は`-2`の形の番号を付ける。"""

    base = created_at.strftime(FOLDER_TIME_FORMAT)
    return base if number == 1 else f"{base}-{number}"


def write_run_output(
    output_dir: Path, created_at: datetime, markdown: str, plan_json: str
) -> Path:
    """出力のフォルダに実行の時刻のフォルダを新しく作り、MarkdownとJSONをUTF-8（BOMなし）で書く。

    作ったフォルダを返す。出力のフォルダがなければ作る。書けなければ`OSError`を送出する。その場合は、
    片方のファイルだけのフォルダが完全な回と見分けられなくならないよう、作ったフォルダを消す。
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    for number in range(1, MAXIMUM_SUFFIX + 1):
        folder = output_dir / run_folder_name(created_at, number)
        try:
            folder.mkdir()
        except FileExistsError:
            continue
        _write_files(folder, {MARKDOWN_NAME: markdown, PLAN_JSON_NAME: plan_json})
        return folder
    raise FileExistsError(
        f"同じ時刻の出力のフォルダが多すぎます: {output_dir / run_folder_name(created_at)}"
    )


def _write_files(folder: Path, files: dict[str, str]) -> None:
    """新しく作ったフォルダへファイルを書く。途中で失敗したら、書いたファイルとフォルダを消す。"""

    try:
        for name, text in files.items():
            (folder / name).write_text(text, encoding="utf-8")
    except OSError as error:
        # 後始末の失敗で、書けなかった理由を隠さない。消せなかった場合はフォルダを示す。
        for name in files:
            with contextlib.suppress(OSError):
                (folder / name).unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            folder.rmdir()
        if folder.exists():
            raise OSError(
                f"{error}。途中まで書いたフォルダを消せませんでした。完全な回ではないため、"
                f"使わずに消してください: {folder}"
            ) from error
        raise
