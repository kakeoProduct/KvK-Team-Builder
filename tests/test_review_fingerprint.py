"""レビューした変更の指紋（ADR 0024）を検証する。"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from review_fingerprint import fingerprint, main  # noqa: E402

# 利用者や実行環境のgitの設定（diff.renames、hookなど）を持ち込まない
GIT_ENVIRONMENT = {
    **{
        key: value
        for key, value in os.environ.items()
        if key not in {"GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"}
    },
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        env=GIT_ENVIRONMENT,
    )
    return result.stdout.strip()


def _commit(repository: Path) -> None:
    _git(repository, "add", "-A")
    _git(repository, "commit", "-q", "--no-verify", "-m", "change")


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """基準のコミットを1つ持つ一時的なRepositoryを作る。"""

    for key in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "reviewer@example.com")
    _git(tmp_path, "config", "user.name", "reviewer")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    # 名前の変更を検出する設定でも、指紋が変わらないことを確かめる
    _git(tmp_path, "config", "diff.renames", "true")
    (tmp_path / ".gitignore").write_text("tmp/\n", encoding="utf-8")
    (tmp_path / "kept.md").write_text("変えない\n", encoding="utf-8")
    (tmp_path / "removed.md").write_text("消す\n", encoding="utf-8")
    (tmp_path / "edited.md").write_text("前\n", encoding="utf-8")
    _commit(tmp_path)
    return tmp_path


def _review_uncommitted(repository: Path) -> tuple[str, str]:
    """編集、削除、追加を含む未コミットの変更を作り、基準と指紋を返す。"""

    base = _git(repository, "rev-parse", "HEAD")
    (repository / "edited.md").write_text("後\n", encoding="utf-8")
    (repository / "removed.md").unlink()
    (repository / "added.md").write_text("新しい\n", encoding="utf-8")
    return base, fingerprint(repository, base)


def test_uncommitted_review_matches_the_commit_that_contains_it(
    repository: Path,
) -> None:
    """レビューした未コミットの変更をそのままコミットすると、指紋が一致する。"""

    base, reviewed = _review_uncommitted(repository)
    _commit(repository)

    assert fingerprint(repository, base, "HEAD") == reviewed


def test_project_memory_records_do_not_change_the_fingerprint(
    repository: Path,
) -> None:
    """レビューの後に記録した共有記憶は、指紋に含めない。"""

    base, reviewed = _review_uncommitted(repository)
    memory = repository / "docs" / "project-memory" / "sessions"
    memory.mkdir(parents=True)
    (memory / "record.md").write_text("記録\n", encoding="utf-8")
    _commit(repository)

    assert fingerprint(repository, base, "HEAD") == reviewed


def test_ignored_files_do_not_change_the_fingerprint(repository: Path) -> None:
    """Git管理外のレビュー結果などは、指紋に含めない。"""

    base, reviewed = _review_uncommitted(repository)
    (repository / "tmp").mkdir()
    (repository / "tmp" / "review.md").write_text("結果\n", encoding="utf-8")

    assert fingerprint(repository, base) == reviewed


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("kept.md", "レビューの後に変えた\n"),
        ("edited.md", "レビューの後にもう一度変えた\n"),
        ("added.md", "レビューの後に足した\n"),
    ],
)
def test_changes_added_after_the_review_change_the_fingerprint(
    repository: Path, path: str, text: str
) -> None:
    """レビューの後に足した修正は、レビュー済みのファイルの内容だけの変更でも検出する。"""

    base, reviewed = _review_uncommitted(repository)
    (repository / path).write_text(text, encoding="utf-8")
    _commit(repository)

    assert fingerprint(repository, base, "HEAD") != reviewed


def test_unstaged_rename_matches_the_commit(repository: Path) -> None:
    """ステージせずに名前を変えた変更も、コミット後の指紋と一致する。"""

    base = _git(repository, "rev-parse", "HEAD")
    (repository / "kept.md").rename(repository / "renamed.md")
    reviewed = fingerprint(repository, base)
    _commit(repository)

    assert fingerprint(repository, base, "HEAD") == reviewed


def test_deleting_the_original_after_reviewing_a_copy_is_detected(
    repository: Path,
) -> None:
    """複製をレビューした後に元のファイルを消すと、名前の変更とみなさずに検出する。"""

    body = "".join(f"行{number}\n" for number in range(40))
    (repository / "kept.md").write_text(body, encoding="utf-8")
    _commit(repository)
    base = _git(repository, "rev-parse", "HEAD")
    (repository / "copy.md").write_text(body + "追加\n", encoding="utf-8")
    reviewed = fingerprint(repository, base)
    (repository / "kept.md").unlink()
    _commit(repository)

    assert fingerprint(repository, base, "HEAD") != reviewed


def test_cli_prints_the_same_fingerprint(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLIは、基準と比べるコミットを受け取り、同じ指紋を出力する。"""

    base, _ = _review_uncommitted(repository)
    _commit(repository)

    assert main(["--base", base, "--target", "HEAD"], root=repository) == 0
    assert capsys.readouterr().out.strip() == fingerprint(repository, base, "HEAD")


def test_cli_reports_an_unknown_base_in_japanese(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """基準のコミットがない場合は、日本語のメッセージで終了コード2を返す。"""

    assert main(["--base", "0" * 40], root=repository) == 2
    error = capsys.readouterr().err
    assert "指紋を計算できません" in error
    # 例外の説明ではなく、gitが出した理由を表示する
    assert "0" * 40 in error
    assert "returned non-zero exit status" not in error


def test_cli_reports_the_error_when_git_prints_nothing(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """gitの標準エラーが空でも、理由を空のままにせず例外の説明を表示する。"""

    def fail(*_: object) -> str:
        raise subprocess.CalledProcessError(128, ["git", "diff"], stderr=b"")

    monkeypatch.setattr("review_fingerprint.fingerprint", fail)
    assert main(["--base", "HEAD"], root=repository) == 2
    assert "returned non-zero exit status 128" in capsys.readouterr().err


def test_cli_rejects_a_commit_that_looks_like_an_option(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """「-」で始まる指定はgitのオプションになり得るため、gitを呼ぶ前に拒否する。"""

    output = repository / "written.txt"
    for argv in (
        [f"--base=--output={output}"],
        ["--base", "HEAD", f"--target=--output={output}"],
    ):
        assert main(argv, root=repository) == 2
        assert "「-」で始まっています" in capsys.readouterr().err
    assert not output.exists()


def test_no_change_matches_a_commit_of_only_project_memory(repository: Path) -> None:
    """変更がない状態の指紋は、共有記憶だけのコミットの後も一致する。"""

    base = _git(repository, "rev-parse", "HEAD")
    reviewed = fingerprint(repository, base)
    memory = repository / "docs" / "project-memory" / "sessions"
    memory.mkdir(parents=True)
    (memory / "record.md").write_text("記録\n", encoding="utf-8")
    _commit(repository)

    assert fingerprint(repository, base, "HEAD") == reviewed
    assert re.fullmatch(r"[0-9a-f]{64}", reviewed)


def test_staged_rename_matches_the_commit(repository: Path) -> None:
    """ステージした名前の変更も、コミット後の指紋と一致する。"""

    base = _git(repository, "rev-parse", "HEAD")
    _git(repository, "mv", "kept.md", "renamed.md")
    reviewed = fingerprint(repository, base)
    _commit(repository)

    assert fingerprint(repository, base, "HEAD") == reviewed
