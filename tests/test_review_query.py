"""レビュー担当が使う確認用Scriptの動作を検証する。"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "tools" / "review_query.py"


def _load() -> ModuleType:
    """確認用Scriptをモジュールとして読み込む。"""

    spec = importlib.util.spec_from_file_location("review_query", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["review_query"] = module
    spec.loader.exec_module(module)
    return module


review_query = _load()


def _git(repository: Path, *arguments: str) -> None:
    """テスト用Repositoryでgitを実行する。"""

    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
    )


def _write(path: Path, content: str) -> None:
    """OSの改行へ変換せずに書く。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


@pytest.fixture(name="repository")
def fixture_repository(tmp_path: Path) -> Path:
    """追跡、未追跡、除外のファイルを持つRepositoryを作る。"""

    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "core.autocrlf", "false")
    _write(tmp_path / ".gitignore", ".env\n")
    _write(tmp_path / "tests" / "test_a.py", "def test_a() -> None:\n    assert True\n")
    _write(tmp_path / "tracked.txt", "alpha\n待機\n")
    _write(tmp_path / "other.txt", "gamma\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "first", "-m", "本文の行")
    _write(tmp_path / "other.txt", "gamma\ndelta\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "second")
    _write(tmp_path / "tracked.txt", "alpha\n待機\nbeta\n")
    _write(tmp_path / "new_dir" / "untracked.txt", "beta\n")
    _write(tmp_path / ".env", "SECRET=beta\n")
    return tmp_path


def _run(
    repository: Path, capfd: pytest.CaptureFixture[str], *arguments: str
) -> tuple[int, str]:
    """Scriptを実行し、終了コードと標準出力を返す。"""

    code = review_query.main(list(arguments), root=repository)
    return code, capfd.readouterr().out


def test_status_and_list_show_each_untracked_file(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """未追跡のディレクトリを畳まず、除外したファイルを出さない。"""

    code, status = _run(repository, capfd, "status")
    assert code == 0
    assert "new_dir/untracked.txt" in status
    assert ".env" not in status

    code, listed = _run(repository, capfd, "list")
    assert code == 0
    assert {"tracked.txt", "new_dir/untracked.txt"} <= set(listed.split())
    assert ".env" not in listed.split()

    code, limited = _run(repository, capfd, "list", "new_dir")
    assert (code, limited.split()) == (0, ["new_dir/untracked.txt"])


def test_grep_searches_untracked_files_but_not_ignored_ones(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """未追跡のファイルも検索し、`.env`は読まない。"""

    code, found = _run(repository, capfd, "grep", "beta")
    assert code == 0
    assert "tracked.txt:3:beta" in found
    assert "new_dir/untracked.txt:1:beta" in found
    assert "SECRET" not in found

    code, japanese = _run(repository, capfd, "grep", "待機", "tracked.txt")
    assert (code, "tracked.txt:2:待機" in japanese) == (0, True)

    # 一致なしはエラーではなく、結果が空であることを示す。
    code, missing = _run(repository, capfd, "grep", "zzz")
    assert (code, missing) == (0, "")


def test_grep_treats_a_pattern_that_looks_like_an_option_as_text(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """`-O`や`--open-files-in-pager`をGitのOptionとして渡さない。"""

    for pattern in ("--open-files-in-pager=sh", "-Osh"):
        code, found = _run(repository, capfd, "grep", "--", pattern)
        assert (code, found) == (0, "")


def test_diff_log_and_show_read_history(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """未コミットの変更を含む差分と、過去の版を読める。"""

    code, diff = _run(repository, capfd, "diff", "--base", "HEAD")
    assert (code, "+beta" in diff) == (0, True)

    code, stat = _run(repository, capfd, "diff", "--base", "HEAD", "--stat")
    assert (code, "tracked.txt" in stat, "+beta" in stat) == (0, True, False)

    code, shown = _run(repository, capfd, "show", "HEAD:tracked.txt")
    assert (code, shown) == (0, "alpha\n待機\n")

    code, older = _run(repository, capfd, "show", "HEAD^:other.txt")
    assert (code, older) == (0, "gamma\n")


def test_grep_uses_extended_expressions_and_optional_case_folding(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """検索語は拡張正規表現で、`--ignore-case`のときだけ大文字小文字を区別しない。"""

    code, either = _run(repository, capfd, "grep", "(alpha|gamma)")
    assert (code, "tracked.txt:1:alpha" in either, "other.txt:1:gamma" in either) == (
        0,
        True,
        True,
    )
    assert _run(repository, capfd, "grep", "ALPHA") == (0, "")
    code, folded = _run(repository, capfd, "grep", "--ignore-case", "ALPHA")
    assert (code, "tracked.txt:1:alpha" in folded) == (0, True)


def test_grep_skips_binary_files(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """バイナリのファイルの内容で出力を乱さない。"""

    (repository / "data.bin").write_bytes(b"epsilon\0")
    assert _run(repository, capfd, "grep", "epsilon") == (0, "")


def test_grep_reports_a_broken_expression_instead_of_no_match(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """Gitのエラーを、一致なしと同じ成功へ畳まない。"""

    code = review_query.main(["grep", "("], root=repository)
    assert code not in {0, review_query.GREP_NO_MATCH}
    assert capfd.readouterr().err != ""


@pytest.mark.parametrize(
    "arguments",
    [("grep", "beta", ".env"), ("list", ".env"), ("grep", "x", "no_such_file")],
)
def test_paths_git_does_not_track_are_errors_not_empty_results(
    repository: Path,
    capfd: pytest.CaptureFixture[str],
    arguments: tuple[str, ...],
) -> None:
    """除外や打ち間違いを「一致なし」と見分けられるようにし、秘密を出さない。"""

    code = review_query.main(list(arguments), root=repository)
    captured = capfd.readouterr()
    assert code != 0, arguments
    assert "SECRET" not in captured.out
    assert "Read" in captured.err


def test_repository_ignores_every_env_file() -> None:
    """`permissions.deny`と同じ範囲の`.env`を、`git grep`の対象から外す。"""

    for name in (".env", ".env.local", ".env.production"):
        completed = subprocess.run(
            ["git", "check-ignore", "-q", name], cwd=PROJECT_ROOT, check=False
        )
        assert completed.returncode == 0, name


def test_log_and_commit_narrow_the_history(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """件数、範囲、パス、本文を指定して履歴を読める。"""

    code, limited = _run(repository, capfd, "log", "--limit", "1")
    assert (code, "second" in limited, "first" in limited) == (0, True, False)

    code, ranged = _run(repository, capfd, "log", "--range", "HEAD~1..HEAD")
    assert (code, "second" in ranged, "first" in ranged) == (0, True, False)

    code, by_path = _run(repository, capfd, "log", "--path", "tracked.txt")
    assert (code, "first" in by_path, "second" in by_path) == (0, True, False)

    code, oneline = _run(repository, capfd, "log")
    assert (code, "本文の行" in oneline) == (0, False)
    code, body = _run(repository, capfd, "log", "--body")
    assert (code, "本文の行" in body) == (0, True)

    code, shown = _run(repository, capfd, "commit", "HEAD")
    assert (code, "second" in shown, "+delta" in shown) == (0, True, True)


def test_diff_narrows_to_a_path_and_compares_from_the_fork_point(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """基準だけにある変更を、逆向きの差分として出さない。"""

    code, narrowed = _run(
        repository, capfd, "diff", "--base", "HEAD~1", "--path", "tracked.txt"
    )
    assert (code, "+beta" in narrowed, "+delta" in narrowed) == (0, True, False)

    _git(repository, "branch", "base")
    _git(repository, "switch", "-q", "-c", "work", "HEAD~1")
    _git(repository, "switch", "-q", "base")
    _write(repository / "only_base.txt", "base\n")
    _git(repository, "add", "only_base.txt")
    _git(repository, "commit", "-q", "-m", "base only")
    _git(repository, "switch", "-q", "work")
    code, diff = _run(repository, capfd, "diff", "--base", "base", "--stat")
    assert (code, "only_base.txt" in diff) == (0, False)


@pytest.mark.parametrize(
    "arguments",
    [
        ("list", "/etc"),
        ("list", "../x"),
        ("list", "a/../../x"),
        ("list", ":(glob)**"),
        ("list", "-x"),
        ("list", "a\\b"),
        ("grep", "x", "/etc"),
        ("grep", "x", ".."),
        ("diff", "--base", "--output=x"),
        ("diff", "--base", "a b"),
        ("diff", "--path", "../x"),
        ("log", "--range", "--output=x"),
        ("show", "--output=x"),
        ("show", "HEAD"),
        ("show", "HEAD:../x"),
        ("show", "HEAD:/etc/passwd"),
        ("test", "src/x.py"),
        ("test", "tests/../x.py"),
        ("test", "--basetemp=src"),
        ("test", "-p"),
        # `=`や`--`を使うとargparseを抜けるため、Script自身の検査が止める。
        ("diff", "--base=--output=x"),
        ("log", "--range=--output=x"),
        ("show", "--", "--output=x:a"),
        ("commit", "--", "--output=x"),
        ("list", "--", "-x"),
        ("list", ""),
        ("diff", "--path=-x"),
        ("log", "--path=../x"),
        ("test", "--", "-p"),
        ("test", "--", "--basetemp=src"),
        ("test", "tests/a.py::a b"),
        ("test", "tests/a.py::$x"),
        ("test", "tests_other/a.py"),
        ("log", "--limit", "0"),
        ("log", "--limit", "-1"),
        ("log", "--limit", "x"),
    ],
)
def test_rejects_arguments_that_leave_the_closed_form(
    repository: Path,
    capfd: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    arguments: tuple[str, ...],
) -> None:
    """Repositoryの外、Option、形の違う値を外部のコマンドへ渡さない。"""

    called: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        called.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(review_query.subprocess, "run", fake_run)
    code = review_query.main(list(arguments), root=repository)
    captured = capfd.readouterr()
    assert code != 0, arguments
    assert called == [], arguments
    assert captured.out == ""
    assert captured.err != ""


@pytest.mark.parametrize(
    "target", ["tests", "tests/a.py", "tests/a.py::C::t[0]", "tests/sub/"]
)
def test_accepts_targets_under_tests(
    repository: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    """`tests/`の下のパスとノードIDは受け付ける。"""

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(review_query.subprocess, "run", fake_run)
    assert review_query.main(["test", target], root=repository) == 0


@pytest.mark.parametrize(
    ("arguments", "returned", "expected"),
    [(["test", "tests/a.py"], 1, 1), (["grep", "x"], 1, 0), (["grep", "x"], 128, 128)],
)
def test_exit_codes_keep_failures_and_only_treat_no_match_as_success(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    returned: int,
    expected: int,
) -> None:
    """テストの失敗を成功へ畳まない。"""

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, returned)

    monkeypatch.setattr(review_query.subprocess, "run", fake_run)
    assert review_query.main(arguments, root=repository) == expected


@pytest.mark.parametrize(
    "arguments", [["status"], ["list", "tracked.txt"], ["grep", "x", "tracked.txt"]]
)
def test_missing_git_is_reported_as_a_message(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    arguments: list[str],
) -> None:
    """起動できないときも、パスの事前確認を含めて例外で終わらない。"""

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(review_query.subprocess, "run", fake_run)
    assert review_query.main(arguments, root=repository) == 2
    assert "実行できません" in capfd.readouterr().err


def test_test_command_runs_real_pytest_and_keeps_its_exit_code(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """本物のpytestを実行し、成功と失敗の終了コードをそのまま返す。"""

    _write(
        repository / "tests" / "test_b.py", "def test_b() -> None:\n    assert False\n"
    )
    code, output = _run(repository, capfd, "test", "tests/test_a.py::test_a")
    assert code == 0
    assert "1 passed" in output
    code, output = _run(repository, capfd, "test", "tests/test_b.py")
    assert code == 1
    assert "1 failed" in output


def test_runs_in_the_repository_with_utf8_fixed_for_children(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """子のpytestとGitへ、Repositoryの位置とUTF-8の出力を渡す。"""

    received: list[dict[str, object]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        received.append(kwargs)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.delenv("PYTHONUTF8", raising=False)
    monkeypatch.setattr(review_query.subprocess, "run", fake_run)
    assert review_query.main(["test", "tests/test_a.py"], root=repository) == 0
    environment = received[0]["env"]
    assert isinstance(environment, dict)
    assert environment["PYTHONUTF8"] == "1"
    assert received[0]["cwd"] == repository


def test_japanese_paths_are_shown_as_is(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """日本語のパスを`"\\345..."`の形へ変えずに示し、そのまま指定できる。"""

    _write(repository / "待機" / "メモ.txt", "epsilon\n")
    for arguments in (["status"], ["list"], ["grep", "epsilon"]):
        code, output = _run(repository, capfd, *arguments)
        assert code == 0, arguments
        assert "待機/メモ.txt" in output, arguments
    code, output = _run(repository, capfd, "grep", "epsilon", "待機/メモ.txt")
    assert code == 0
    assert "待機/メモ.txt:1:epsilon" in output


def test_rejects_unknown_subcommand_and_option(
    repository: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """定義していない操作とOptionを受け付けない。"""

    for arguments in (["commit"], ["status", "--output=x"], ["grep"], []):
        code = review_query.main(arguments, root=repository)
        capfd.readouterr()
        assert code != 0, arguments


def test_test_command_runs_pytest_with_fixed_options(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """渡すのは`tests/`の下のパスとノードIDだけで、Optionは固定する。"""

    called: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        called.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(review_query.subprocess, "run", fake_run)
    assert review_query.main(["test", "tests/test_a.py::test_a"], root=repository) == 0
    assert called == [
        [sys.executable, "-m", "pytest", "-q", "--", "tests/test_a.py::test_a"]
    ]


@pytest.mark.parametrize(
    ("arguments", "required"),
    [
        (["diff", "--base", "dev"], ["--no-ext-diff", "--no-textconv"]),
        (["diff", "--base", "dev"], ["--merge-base", "dev"]),
        (["show", "HEAD:a.txt"], ["--no-ext-diff", "--no-textconv"]),
        (["commit", "HEAD"], ["--no-ext-diff", "--no-textconv"]),
        (["status"], ["-c", "core.quotePath=false"]),
        (["grep", "--", "-e"], ["-e", "-e"]),
        (["list", "a.txt"], ["--", "a.txt"]),
    ],
)
def test_git_receives_options_that_do_not_run_other_programs(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    required: list[str],
) -> None:
    """外部diffとtextconvを起動せず、検索語は`-e`の値として渡す。"""

    called: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        called.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(review_query.subprocess, "run", fake_run)
    monkeypatch.setattr(review_query, "_ensure_paths_have_files", lambda *_: None)
    assert review_query.main(arguments, root=repository) == 0
    command = called[0]
    assert command[:3] == ["git", "--no-pager", "--no-optional-locks"]
    joined = " ".join(command)
    assert " ".join(required) in joined


def test_outside_a_repository_fails_with_a_message(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """Gitの失敗を例外にせず、終了コードとメッセージで返す。"""

    assert review_query.main(["status"], root=tmp_path) != 0
    assert capfd.readouterr().err != ""


def test_script_runs_from_the_command_line() -> None:
    """Hookが許可する`tools/review_query.py`の相対パスで起動できる。"""

    completed = subprocess.run(
        [sys.executable, "tools/review_query.py", "show", "HEAD:AGENTS.md"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "開発ルール".encode() in completed.stdout
