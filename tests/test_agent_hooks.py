"""Claude CodeとCodexで共有するAgent Hookの振る舞いテスト。"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOK_DIRECTORY = PROJECT_ROOT / "tools" / "hooks"
GIT_GUARD_SCRIPT = HOOK_DIRECTORY / "block_dangerous_git.py"
MEMORY_HOOK_SCRIPT = HOOK_DIRECTORY / "project_memory_hook.py"
READ_ONLY_AGENT_SCRIPT = HOOK_DIRECTORY / "enforce_read_only_agent.py"
BROWSER_FILE_SCRIPT = HOOK_DIRECTORY / "restrict_browser_files.py"
PROJECT_MEMORY_SCRIPT = (
    PROJECT_ROOT
    / ".agents"
    / "skills"
    / "maintain-project-memory"
    / "scripts"
    / "session_memory.py"
)
CLAUDE_SETTINGS_PATH = PROJECT_ROOT / ".claude" / "settings.json"


def _run_hook(
    script: Path, payload: object, *arguments: str, cwd: Path = PROJECT_ROOT
) -> subprocess.CompletedProcess[str]:
    """Hook ScriptへJSONを標準入力として渡して実行する。"""

    return subprocess.run(
        [sys.executable, str(script), *arguments],
        input=json.dumps(payload),
        cwd=cwd,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def _git_guard_decision(command: str, *arguments: str) -> tuple[str, str] | None:
    """Git保護Hookの判定と理由を返す。許可時はNoneを返す。"""

    completed = _run_hook(
        GIT_GUARD_SCRIPT,
        {"hook_event_name": "PreToolUse", "tool_input": {"command": command}},
        *arguments,
    )
    assert completed.returncode == 0, completed.stderr
    if completed.stdout == "":
        return None
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    return output["permissionDecision"], output["permissionDecisionReason"]


def test_git_guard_denies_destructive_commands_by_default() -> None:
    """既定動作ではpushと作業内容を失う操作をすべて拒否する。"""

    for command, label in (
        ("git push origin main", "git push"),
        ("git -C repo push", "git push"),
        ("git reset --hard HEAD~1", "git reset --hard"),
        ("git clean -fd", "git clean -f"),
        ("git branch -D temporary", "git branch -D"),
        ("git checkout .", "git checkout ."),
        ("git restore -- .", "git restore ."),
        ("git worktree remove --force ../other", "git worktree remove --force"),
        ("git worktree remove -f .worktrees/topic", "git worktree remove --force"),
    ):
        decision = _git_guard_decision(command)
        assert decision is not None
        assert decision[0] == "deny"
        assert label in decision[1]

    assert _git_guard_decision("git status") is None
    assert _git_guard_decision('git commit -m "feat(hooks): 日本語の要約"') is None
    assert _git_guard_decision("git worktree add -b topic .worktrees/topic") is None
    assert _git_guard_decision("git worktree remove .worktrees/topic") is None


def test_git_guard_asks_for_normal_push_but_denies_force_push() -> None:
    """Claude Code用の確認モードでは通常pushだけを利用者確認へ回す。"""

    decision = _git_guard_decision("git push -u origin feature", "--ask-push")
    assert decision is not None
    assert decision[0] == "ask"
    assert "git push" in decision[1]

    for command in (
        "git push --force origin feature",
        "git push -f origin feature",
        "git push --force-with-lease",
        "git push origin +feature",
    ):
        decision = _git_guard_decision(command, "--ask-push")
        assert decision is not None, command
        assert decision[0] == "deny", command
        assert "git push --force" in decision[1]

    reset = _git_guard_decision("git status && git reset --hard", "--ask-push")
    assert reset is not None
    assert reset[0] == "deny"


def test_git_guard_judges_sections_it_cannot_tokenize() -> None:
    """字句解析できない区間も、語に分けて同じ判定にかける。"""

    for command in (
        "git reset --hard # it's fine",
        'git push --force "a;b"',
        'git clean -fd "a;b"',
        "git branch -D x # it's gone",
        "git status # C:\\work\\\ngit reset --hard",
        "echo \\\\\ngit reset --hard",
        'git -c user.name="A B" reset --hard # it\'s fine',
        'git "reset" --hard # it\'s fine',
        # 通常のpushが先にあっても、後ろの拒否を確認へ下げない。
        "git push origin x && git reset --hard",
        'git push "a;b" --force',
        'git push origin "+main;x"',
        'git "push" --force "a;b"',
        # 引用符の中の空白で語が分かれると、Gitの大域Optionの値を読み違える。
        'git -C "my dir" reset --hard # it\'s fine',
        # 行継続は1つのコマンドであり、改行で区切らない。
        "git reset \\\n--hard",
        "git reset \\\r\n--hard",
        "git push \\\n--force origin x",
        # 引用符の中でも、Shellが実行する文字列は区切って判定する。
        "bash -c 'cd /x && git reset --hard && echo ok'",
        'sh -c "git fetch; git reset --hard origin/dev; git clean -fd"',
        "bash -lc 'git status; git reset --hard'",
        "/bin/zsh -c 'git status | git reset --hard'",
        'echo "$(git status; git reset --hard; date)"',
        "echo `git status; git reset --hard`",
        'bash -c "echo $(git status; git reset --hard)"',
        # 単独の`&`も区切りである。
        "git status & git reset --hard",
        # `-c`の前のOptionと`eval`。
        "bash --login -c 'cd /x && git reset --hard && echo ok'",
        "bash -e -o pipefail -c 'git fetch && git reset --hard && echo ok'",
        "eval 'git fetch && git reset --hard origin/dev && echo ok'",
        'echo "$(git status; (git reset --hard))"',
        # 引用符の範囲は`\\`の退避と改行をまたぐ引用符を含めて決める。
        'git commit -m "fix: x\n\nbody" && git push --force && echo "done"',
        "git commit -m 'don'\\''t panic' && git push --force && echo 'pushed'",
        'git commit -m "say \\"hi" && git push --force && echo "ok"',
        "echo 'it'\\''s'; git reset --hard; echo 'x'",
        # 変更前の照合が拒否していた入力は、引用符の解釈にかかわらず拒否する。
        "git status # it's ok\ngit reset --hard\ngit log -1 # that's all",
        "# Let's push\ngit push --force origin x\n# that's it",
        "git commit -F - <<'E'\ndon't stop\nE\ngit reset --hard\n# it's done",
        "cat > a <<'E'\ndon't\nE\ngit reset --hard\ncat > b <<'E'\nwon't\nE",
        "echo \"$(echo ')'; git reset --hard; echo ok)\"",
        "echo \"$(echo '('; git reset --hard; echo ok)\"",
        "echo $'don\\'t'; git reset --hard; echo ok\\'s",
        'echo "a\\"b" ; git reset --hard ; echo "c\\"d"',
        "echo it\\'s ; git reset --hard ; echo that\\'s",
        'echo "$( (cd /x); git reset --hard )"',
        "bash -euo pipefail -c 'git fetch && git reset --hard && echo ok'",
        "bash +e -c 'git fetch; git reset --hard; echo ok'",
        "bash --rcfile x -c 'git fetch; git reset --hard; echo ok'",
        "bash -c -x 'git fetch && git reset --hard && echo ok'",
        "sh -c -- 'git fetch; git reset --hard; true'",
        "echo 'git fetch; git reset --hard; echo ok' | bash",
        "bash <<< 'git fetch; git reset --hard; echo ok'",
        "bash <<'E'\necho it's\ngit reset --hard\necho that's\nE",
        'pwsh -Command "git fetch; git reset --hard origin/dev; echo ok"',
        'cmd /c "git fetch && git reset --hard && echo ok"',
        'Get-ChildItem "C:\\work\\"; git reset --hard; Get-ChildItem "C:\\tmp\\"',
        "git -c alias.x='!git fetch; git reset --hard; true' x",
        "echo $($($($($($($($($(true;git reset --hard;true)))))))))",
    ):
        decision = _git_guard_decision(command, "--ask-push")
        assert decision is not None and decision[0] == "deny", command

    for command in (
        'git push origin "a;b"',
        'git commit -m "fix: x\n\nbody" && git push -u origin "$BRANCH"',
        "# Let's push\ngit push origin x\n# Don't forget",
    ):
        pushed = _git_guard_decision(command, "--ask-push")
        assert pushed is not None and pushed[0] == "ask", command

    # 日常のコマンドを止めない。本文の引用符で字句解析に失敗することは珍しくない。
    for command in (
        'git commit -m "a;b"',
        "git status # it's fine",
        "echo it's fine",
        "python - <<'E'\nprint(\"it's\")\nE",
        "git commit -F - <<'E'\nfix: don't stop\nE",
        # 引用符の中の区切りは、コマンドの区切りではない。
        'git commit -m "a; git reset --hard"',
        "python tools/review_query.py grep 'git push|git reset --hard' tools/",
        "bash -c 'git status; git log -1'",
        'echo "$(git rev-parse HEAD; date)"',
        "python tools/check.py 2>&1 | tail -5",
        # 単一引用符の中のバッククォートは実行されない。
        "git commit -m 'docs: `git reset --hard`の説明'",
        "bash -e -o pipefail -c 'git fetch && git log -1'",
        # コメントの中のバッククォートは実行されない。
        "ls # `git reset --hard`は使わない",
        # 引用符付きのヒアドキュメントで渡すコミットの本文は展開されない。
        "git commit -m \"$(cat <<'EOF'\nfix: `git push`の前に確かめる\nEOF\n)\"",
        "git commit -m \"$(cat <<'EOF'\nfix: `git reset --hard`を止める\nEOF\n)\"",
        "git commit -F - <<'E'\nfix: `git reset --hard`を止める\nE",
        # 本文の引用符の中の区切りと、対にならない括弧は、本文の外へ影響しない。
        "python - <<'E'\nprint(\"a; git reset --hard\")\nE",
        'git commit -m "$(cat <<\'EOF\'\nfix: "a; git reset --hard" を止める\nEOF\n)"',
        "git commit -m \"$(cat <<'EOF'\nfix: 1) `git push`の前に確かめる\nEOF\n)\"",
        "git commit -m \"$(cat <<'EOF'\nfix: (注 `git reset --hard`を止める\nEOF\n)\"",
        # 引用符の中の改行は区切りではない。
        'git commit -m "fix: x\ngit reset --hard"',
    ):
        assert _git_guard_decision(command, "--ask-push") is None, command


def _load_git_guard() -> ModuleType:
    """Git保護Hookをモジュールとして読み込む。"""

    spec = importlib.util.spec_from_file_location(
        "block_dangerous_git", GIT_GUARD_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_git_guard_quote_aware_judgment_finds_each_hidden_operation() -> None:
    """引用符を解釈する判定の各処理を、変更前と同じ判定から独立に確かめる。

    どの入力も、変更前と同じ判定（区切りで分けて字句解析に失敗した区間を読み飛ばす）では
    `git reset --hard`の区間を作れない。引用符を解釈する判定の処理が壊れると失敗する。
    """

    guard = _load_git_guard()
    target = ["git", "reset", "--hard"]
    for command in (
        # 二重引用符の中の`\"`と、引用符の外の`\'`の退避。退避を読み違えると引用符が偶数個で
        # 閉じ、閉じない引用符の処理へ戻らずに`git reset --hard`を隠す。
        'git commit -m "a\\"b" & git reset --hard & echo "c\\"d"',
        "echo it\\'s & git reset --hard & echo that\\'s",
        # コメントの中の`'`は引用符ではない。
        "git status # it's\ngit reset --hard & echo 'a;b' # that's",
        # 値を取るOptionの後の`-c`、`eval`、置換、語の途中の`#`。
        "bash -e -o pipefail -c 'git reset --hard'",
        # bashは`-c`の後もOptionを読み、Optionでない最初の語を文字列とする。
        "bash -euo pipefail -c 'git reset --hard'",
        "bash --rcfile x -c 'git reset --hard'",
        "bash +e -c 'git reset --hard'",
        "bash -c -x 'git reset --hard'",
        "sh -c -- 'git reset --hard'",
        "bash -c - 'git reset --hard'",
        "bash -O extglob -c 'git reset --hard'",
        "bash --init-file x -c 'git reset --hard'",
        "eval 'git reset --hard'",
        # 引用符のないヒアドキュメントの本文の置換は実行される。
        "cat <<EOF\n$(git reset --hard)\nEOF",
        # ヒアストリングは本文を持たないため、次の行を本文として読み飛ばさない。
        "cat <<< 'x'\necho `git reset --hard`",
        # 区切りの行で本文を終え、その後の行を判定に戻す。
        "cat <<'E'\nx\nE\ntrue\necho `git reset --hard`",
        "cat <<-'E'\n\tx\n\tE\ntrue\necho `git reset --hard`",
        "cat <<'A' <<'B'\nx\nA\ny\nB\ntrue\necho `git reset --hard`",
        "cat <<'E'\r\nx\r\nE\r\ntrue\r\necho `git reset --hard`",
        # 区切りの語の途中で引用符が終わる形は、ヒアドキュメントとして扱わない。
        "cat <<'E'OF\nx\nEOF\necho `git reset --hard`",
        # 置換の中の引用符にある括弧は、置換の範囲を決める括弧ではない。
        "echo \"$(echo ')' ; git reset --hard)\"",
        "echo \"$(echo '(' ; git reset --hard)\"",
        'echo "$(echo ")" ; git reset --hard)"',
        # 置換の中の`\)`は括弧ではなく、置換を閉じた後は外側の引用符の状態へ戻る。
        'echo "$(echo \\) ; git reset --hard)"',
        'echo "$(true) # $(git reset --hard)"',
        # 本文をShellへ渡すと、本文の置換は実行される。
        "bash <<'EOF'\necho \"$(git reset --hard)\"\nEOF",
        "cat <<'EOF' | sh\necho $(git reset --hard)\nEOF",
        "true && bash <<'E'\necho `git reset --hard`\nE",
        # 区間の始まりは、`;`、`|`、改行、ヒアドキュメントの本文の後で変わる。
        "echo a; bash <<'E'\necho `git reset --hard`\nE",
        "echo a | bash <<'E'\necho `git reset --hard`\nE",
        "echo a\nbash <<'E'\necho `git reset --hard`\nE",
        # 引用符の中の区切りでは、区間の始まりは変わらない。
        "bash -s \"a;b\" <<'E'\necho `git reset --hard`\nE",
        "cat <<'A'\nx\nA\nbash <<'B'\necho `git reset --hard`\nB",
        # パイプの有無は行ごとに判定し直す。
        "cat <<'A'\nx\nA\ncat <<'B' | sh\necho `git reset --hard`\nB",
        "(bash <<'E'\necho `git reset --hard`\nE\n)",
        "/bin/bash <<'E'\necho `git reset --hard`\nE",
        # 閉じない引用符で元の文へ戻す処理と、`-c`の文字列の中で隠した区切りを戻す処理。
        "echo it's & git reset --hard",
        "bash -c 'git status & git reset --hard'",
        'echo "$(git reset --hard)"',
        "echo a#$(git reset --hard)",
        'echo "# $(git reset --hard)"',
    ):
        assert target not in list(guard._plain_segments(command)), command
        assert target in list(guard._command_segments(command)), command

    # 単一引用符、コメント、引用符付きのヒアドキュメントの本文の置換は実行されない。
    for command in (
        "echo '$(git reset --hard)'",
        "ls # `git reset --hard`",
        "cat <<'EOF'\n`git reset --hard`\nEOF",
        'cat <<"EOF"\n$(git reset --hard)\nEOF',
        "cat <<-\\EOF\n\t`git reset --hard`\n\tEOF",
        # `-`がなければ、タブ付きの行は区切りではない。区切りがなければ本文は最後まで続く。
        "cat <<'E'\n\tE\n`git reset --hard`\nE",
        "cat <<'EOF'\n`git reset --hard`",
        "cat <<'A' <<'B'\nx\nA\n`git reset --hard`\nB",
        # Shellへのパイプは、ヒアドキュメントの記号と同じ行だけを見る。本文の`| sh`は対象外。
        "cat <<'E'\nx | sh\n`git reset --hard`\nE",
        "echo a; cat <<'E'\n`git reset --hard`\nE",
        "bash -c true; cat <<'E'\n`git reset --hard`\nE",
        "bash <<'A'\ntrue\nA\ncat <<'B'\n`git reset --hard`\nB",
        "cat <<'A' | sh\nx\nA\ncat <<'B'\n`git reset --hard`\nB",
    ):
        assert target not in list(guard._command_segments(command)), command

    # 行継続がなければ、同じ区間を2回返さない。
    assert list(guard._command_segments("git status")) == [["git", "status"]]


def test_git_guard_matches_parens_outside_quotes_comments_and_heredocs() -> None:
    """`$(`の範囲は、引用符、コメント、引用符付きの本文の括弧で閉じない。"""

    guard = _load_git_guard()
    for command in (
        "$(echo ')')",
        '$(echo ")")',
        "$(# )\n)",
        "$(cat <<'E'\n1)\nE\n)",
        "$(echo \\))",
    ):
        assert guard._matching_parens(command) == {1: len(command) - 1}, command
    # `$(`の中では、外側の二重引用符と別に引用符の状態を数える。
    command = '"$(echo "a")"'
    assert guard._matching_parens(command) == {2: len(command) - 2}


def test_git_guard_plain_judgment_matches_the_previous_splitting() -> None:
    """変更前と同じ判定は、すべての区切りで分け、字句解析に失敗した区間を読み飛ばす。"""

    guard = _load_git_guard()
    assert list(guard._plain_segments('git commit -m "a; git reset --hard"')) == []
    assert list(guard._plain_segments("echo 'a;b' && git reset --hard")) == [
        ["git", "reset", "--hard"]
    ]


def test_git_guard_quote_aware_judgment_runs_in_linear_time() -> None:
    """引用符を解釈する判定の時間が、入力の長さの2乗で増えない。

    `_blocked_operation`は長い入力でこの判定を行わないため、判定の関数を直接呼んで確かめる。
    """

    guard = _load_git_guard()
    for command in (
        "echo " + "$(" * 20000 + " x",
        # ヒアドキュメントの記号が並んでも、本文をShellへ渡すかの判定を毎回やり直さない。
        "git push origin x; cat " + "<<'a' " * 20000,
        # パイプの検索と、区間の最初の語の判定も、記号ごとに先頭から読み直さない。
        "git push origin x; cat <<'a' " + "|" * 200000,
        "git push origin x; " + "(" * 100000 + "cat " + "<<'a' " * 20000,
        # `-c`を探す走査は、走査済みの語から始め直さない。
        "git push origin x; " + "bash -o " * 25000,
    ):
        started = time.perf_counter()
        list(guard._command_segments(command))
        assert time.perf_counter() - started < 5


def test_git_guard_judges_long_input_only_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """上限を超える長さの入力は、ADR 0033より前と同じ判定だけで判定する。"""

    guard = _load_git_guard()
    hidden = "; echo `git reset --hard`"
    limit = guard.MAX_QUOTE_AWARE_LENGTH
    assert guard._blocked_operation("x" * (limit - len(hidden)) + hidden) == (
        "git reset --hard"
    )
    assert guard._blocked_operation("x" * (limit - len(hidden) + 1) + hidden) is None
    # ADR 0033より前と同じ判定は、長さにかかわらず行う。
    assert guard._blocked_operation("x" * limit + "; git reset --hard") == (
        "git reset --hard"
    )

    # 上限を超えると、引用符を解釈する判定を呼ばない。
    called: list[int] = []
    original = guard._command_segments

    def recording(command: str, depth: int = 0) -> Iterator[list[str]]:
        called.append(len(command))
        return original(command, depth)

    monkeypatch.setattr(guard, "_command_segments", recording)
    guard._blocked_operation("x" * (limit + 1))
    assert called == []
    guard._blocked_operation("x" * limit)
    assert called == [limit]


def test_git_guard_misses_above_the_limit_only_what_adr_0033_accepts() -> None:
    """上限を超えた入力で見逃す形と止める形を、ADR 0033の影響の一覧のとおりに固定する。

    見逃す形は、利用者が2026-11-08に受け入れた範囲である（ADR 0033より前も見逃す）。
    """

    guard = _load_git_guard()
    padding = "x" * guard.MAX_QUOTE_AWARE_LENGTH + "\n"
    for missed in (
        "echo $(git reset --hard)",
        "echo `git reset --hard`",
        "sh -c 'git reset --hard'",
        "eval 'git reset --hard'",
        "(git reset --hard)",
        "git reset --hard # don't",
        "true&git reset --hard",
    ):
        assert guard._blocked_operation(padding + missed) is None, missed
    for stopped in (
        "cat <<'E'\ngit reset --hard\nE",
        "eval git reset --hard",
    ):
        assert guard._blocked_operation(padding + stopped) == "git reset --hard", (
            stopped
        )


def test_git_guard_keeps_push_confirmation_near_the_limit() -> None:
    """`bash -o`の並びでも、上限の前後で通常のpushの確認を時間内に返す。"""

    guard = _load_git_guard()
    prefix = "git push origin x; "
    words = (guard.MAX_QUOTE_AWARE_LENGTH - len(prefix)) // len("bash -o ")
    for count in (words, words + 1):
        command = prefix + "bash -o " * count
        started = time.perf_counter()
        assert guard._blocked_operation(command) == "git push"
        assert time.perf_counter() - started < 5


def test_git_guard_resumes_shell_scan_after_skipped_option_values() -> None:
    """`-c`の走査は、読み飛ばしたOptionの値の次の語から続ける。"""

    guard = _load_git_guard()
    tokens = ["bash", "-o", "pipefail", "bash", "-c", "git reset --hard"]
    assert guard._shell_script(tokens) == "git reset --hard"


def test_git_guard_fails_closed_on_unreadable_input() -> None:
    """Hook入力を解析できない場合は安全側へ拒否する。"""

    completed = subprocess.run(
        [sys.executable, str(GIT_GUARD_SCRIPT)],
        input="not json",
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"


def _read_only_decision(payload: object) -> tuple[str, str] | None:
    """読み取り専用AgentのHook判定と理由を返す。許可時はNoneを返す。"""

    completed = _run_hook(READ_ONLY_AGENT_SCRIPT, payload)
    assert completed.returncode == 0, completed.stderr
    if completed.stdout == "":
        return None
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    return output["permissionDecision"], output["permissionDecisionReason"]


def _tool_payload(tool_name: str, tool_input: dict[str, object]) -> dict[str, object]:
    """Subagent内のPreToolUse入力を作る。"""

    return {
        "hook_event_name": "PreToolUse",
        "agent_type": "kvk-test-reviewer",
        "permission_mode": "auto",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }


def _bash_decision(command: str) -> tuple[str, str] | None:
    """Bashコマンドに対する読み取り専用Hookの判定を返す。"""

    return _read_only_decision(_tool_payload("Bash", {"command": command}))


def test_read_only_agent_allows_only_the_review_query_grammar() -> None:
    """固定のScriptの呼び出しだけを、閉じた文法で通す（ADR 0033）。"""

    for command in (
        "python tools/review_query.py status",
        "python tools/review_query.py list src/",
        "python tools/review_query.py grep 'A > B >= C' docs/",
        "python tools/review_query.py grep '^def (foo|bar)$; rm x' tests/",
        "python tools/review_query.py grep '待機' src/ tests/",
        "python tools/review_query.py diff --base HEAD~1 --stat",
        "python tools/review_query.py show HEAD^:README.md",
        "python tools/review_query.py test tests/test_parser.py::test_x",
        "python tools/review_query.py --help",
        "python tools/review_query.py log --range dev..HEAD --path=src/",
        "python tools/review_query.py log --range dev..HEAD~1",
        "python tools/review_query.py grep 'a=~/x'",
        # 文字の集合の境界と、`-`で始まる検索語の書き方。
        "python tools/review_query.py grep -- -Osh",
        "python tools/review_query.py log --range a@b",
        "python tools/review_query.py grep a,b+c%d",
    ):
        assert _bash_decision(command) is None, command


def test_read_only_agent_denies_shell_outside_the_grammar() -> None:
    """Shellが解釈する記法と、固定のScript以外のコマンドを拒否する。"""

    for command in (
        "",
        " python tools/review_query.py status",
        "python tools/review_query.py",
        "python tools/review_query.py  status",
        "python tools/review_query.py status ",
        "python tools/review_query.py\tstatus",
        "python tools/review_query.py status\nrm README.md",
        "python tools/review_query.py status; rm README.md",
        "python tools/review_query.py status && rm README.md",
        "python tools/review_query.py status | sh",
        "python tools/review_query.py status > README.md",
        "python tools/review_query.py status &",
        "python tools/review_query.py status #",
        "python tools/review_query.py grep $HOME",
        "python tools/review_query.py grep ${HOME}",
        "python tools/review_query.py grep $(rm README.md)",
        "python tools/review_query.py grep `rm README.md`",
        "python tools/review_query.py grep {a,b}",
        "python tools/review_query.py grep a*",
        "python tools/review_query.py grep 待機",
        "python tools/review_query.py list ~",
        "python tools/review_query.py list ~/x",
        # bashは代入の形の引数でも、`=`と`:`の直後の`~`を展開する。
        "python tools/review_query.py list a=~/x",
        "python tools/review_query.py list a=b:~/x",
        "python tools/review_query.py log --range=~/x",
        *(
            f"python tools/review_query.py grep a{symbol}b"
            for symbol in '<>"()?[]\\!{}$`;|&#*'
        ),
        "python tools/review_query.py status\n",
        "python tools/review_query.py status\r\n",
        "python tools/review_query.py grep 'a\rb'",
        'python tools/review_query.py grep "$(rm README.md)"',
        "python tools/review_query.py grep $'a'",
        "python tools/review_query.py grep 'a'b",
        "python tools/review_query.py grep a'b'",
        "python tools/review_query.py grep 'unterminated",
        "python tools/review_query.py grep 'a\nb'",
        "python3 tools/review_query.py status",
        "python ./tools/review_query.py status",
        "python tools/review_query.pyc status",
        "python -c 'open(1)' tools/review_query.py status",
        "FOO=1 python tools/review_query.py status",
        "cd tests && python tools/review_query.py status",
        "git status --short",
        "cat README.md",
        "python -m pytest tests/test_parser.py -q",
        "python tools/check.py",
        # 文字列の照合では見分けられなかった書き込みの経路。
        "ls $'a\\'' ; rm README.md \\'",
        "find . -name x $'-delete'",
        "find . -name x {-delete,}",
        "git log --out${nothing}put=x",
        "git grep --open=rm x",
        "git grep -iOrm x",
        "sort --outp=x f",
        "sort -uox f",
        "sort --compress-program=x f",
        "ls a#b ; rm README.md",
    ):
        decision = _bash_decision(command)
        assert decision is not None and decision[0] == "deny", command
        assert "python tools/review_query.py" in decision[1]
        assert "単一引用符" in decision[1]


def test_read_only_agent_denies_bash_without_a_command() -> None:
    """コマンドを確かめられないBashは拒否する。"""

    for tool_input in ({}, {"command": 1}, {"command": None}):
        decision = _read_only_decision(_tool_payload("Bash", tool_input))
        assert decision is not None and decision[0] == "deny", tool_input
    for value in ("git status", None):
        decision = _read_only_decision(
            {**_tool_payload("Bash", {}), "tool_input": value}
        )
        assert decision is not None and decision[0] == "deny", value


def test_read_only_agent_denies_writes_in_any_permission_mode() -> None:
    """権限モードにかかわらず、書き込み得るToolをすべて拒否する。"""

    for tool_name, tool_input in (
        ("FutureTool", {}),
        ("Edit", {"file_path": "README.md"}),
        ("Write", {"file_path": "x.md", "content": ""}),
        ("NotebookEdit", {"notebook_path": "x.ipynb"}),
        ("Agent", {"prompt": "edit files"}),
        ("PowerShell", {"command": "New-Item x"}),
        ("Monitor", {"command": "touch x"}),
        ("mcp__example__write", {}),
        # ブラウザ操作は画面写真を書き得るため、レビュー担当には使わせない（ADR 0032）。
        ("mcp__playwright__browser_navigate", {"url": "http://127.0.0.1:8765/"}),
    ):
        for mode in ("default", "plan", "auto", "acceptEdits", "bypassPermissions"):
            payload = {**_tool_payload(tool_name, tool_input), "permission_mode": mode}
            decision = _read_only_decision(payload)
            assert decision is not None and decision[0] == "deny", (tool_name, mode)
            assert f"{tool_name}は読み取り専用のAgentで使用できません" in decision[1]


def test_read_only_agent_fails_closed_on_unreadable_input() -> None:
    """Hook入力やTool名を解析できない場合は拒否する。"""

    completed = subprocess.run(
        [sys.executable, str(READ_ONLY_AGENT_SCRIPT)],
        input="not json",
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"

    for payload in (
        {"hook_event_name": "PreToolUse", "agent_type": "kvk-test-reviewer"},
        {
            "hook_event_name": "PreToolUse",
            "agent_type": "kvk-test-reviewer",
            "tool_name": "Bash",
            "tool_input": {},
        },
    ):
        decision = _read_only_decision(payload)
        assert decision is not None and decision[0] == "deny", payload


def test_read_only_agent_denies_tool_name_that_is_not_text() -> None:
    """文字列でないTool名は、値を理由の文へ埋め込まずに拒否する。"""

    decision = _read_only_decision(
        {
            "hook_event_name": "PreToolUse",
            "agent_type": "kvk-test-reviewer",
            "tool_name": ["Edit"],
        }
    )
    assert decision is not None and decision[0] == "deny"
    assert "Tool名を確認できませんでした" in decision[1]
    assert "Edit" not in decision[1]


def test_read_only_agent_denies_agent_type_that_is_not_text() -> None:
    """`agent_type`がないのは主Sessionだが、文字列でない値は対象を確かめられない。"""

    base = {"hook_event_name": "PreToolUse", "tool_name": "Edit"}
    for agent_type in (["kvk-test-reviewer"], [], 0, False, {}):
        decision = _read_only_decision({**base, "agent_type": agent_type})
        assert decision is not None and decision[0] == "deny", agent_type
        assert "Agentを確認できませんでした" in decision[1]

    assert _read_only_decision(base) is None
    assert _read_only_decision({**base, "agent_type": None}) is None


def test_safety_hooks_deny_payload_of_unexpected_shape() -> None:
    """JSONとして読めても、形の違う入力は判定できないため拒否する。"""

    for script, payload in (
        (GIT_GUARD_SCRIPT, []),
        (GIT_GUARD_SCRIPT, {"hook_event_name": "Other", "tool_input": {}}),
        (GIT_GUARD_SCRIPT, {"hook_event_name": "PreToolUse"}),
        (READ_ONLY_AGENT_SCRIPT, []),
        (GIT_GUARD_SCRIPT, {"hook_event_name": "PreToolUse", "tool_input": {}}),
        (
            GIT_GUARD_SCRIPT,
            {"hook_event_name": "PreToolUse", "tool_input": {"command": 1}},
        ),
        (READ_ONLY_AGENT_SCRIPT, {"tool_name": "Bash"}),
        (READ_ONLY_AGENT_SCRIPT, {"hook_event_name": "Other", "tool_name": "Bash"}),
    ):
        completed = _run_hook(script, payload)
        assert completed.returncode == 0, completed.stderr
        output = json.loads(completed.stdout)["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny", (script.name, payload)


def test_safety_hooks_deny_input_that_stops_the_json_parser() -> None:
    """例外で終わるとClaude CodeはToolを通すため、深い入れ子と巨大な整数も拒否する。"""

    deep_nesting = b"[" * 200_000
    # 主Sessionの`git status`にし、整数を読めれば3つのHookとも許可する本文にする。
    body_with = (
        b'{"hook_event_name": "PreToolUse", "tool_name": "Bash", '
        b'"tool_input": {"command": "git status", "value": %s}}'
    )
    huge_integer = body_with % (b"1" * 5_000)
    for script in (GIT_GUARD_SCRIPT, READ_ONLY_AGENT_SCRIPT, BROWSER_FILE_SCRIPT):
        for body in (deep_nesting, huge_integer):
            completed = subprocess.run(
                [sys.executable, str(script)],
                input=body,
                cwd=PROJECT_ROOT,
                capture_output=True,
                check=False,
            )
            assert completed.returncode == 0, (script.name, completed.stderr[-200:])
            output = json.loads(completed.stdout)["hookSpecificOutput"]
            assert output["permissionDecision"] == "deny", script.name

        allowed = subprocess.run(
            [sys.executable, str(script)],
            input=body_with % b"1",
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=False,
        )
        assert (allowed.returncode, allowed.stdout) == (0, b""), script.name


def test_read_only_hook_restricts_agent_whose_definition_is_broken(
    tmp_path: Path,
) -> None:
    """定義を読めないAgentは、読み取り専用の宣言を確かめられないため制限する。"""

    hook = tmp_path / "tools" / "hooks" / READ_ONLY_AGENT_SCRIPT.name
    hook.parent.mkdir(parents=True)
    shutil.copy2(READ_ONLY_AGENT_SCRIPT, hook)
    definition = tmp_path / ".codex" / "agents" / "kvk-test-reviewer.toml"
    definition.parent.mkdir(parents=True)

    for content in (b"\xff", b"sandbox_mode = ", b"x = " + b"[" * 200_000):
        definition.write_bytes(content)
        completed = _run_hook(
            hook,
            {
                "hook_event_name": "PreToolUse",
                "agent_type": "kvk-test-reviewer",
                "tool_name": "Edit",
            },
        )
        assert completed.returncode == 0, completed.stderr
        output = json.loads(completed.stdout)["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny", content[:20]

    # 読める定義なら宣言に従い、読み取り専用でないAgentは制限しない。
    definition.write_bytes(b'sandbox_mode = "workspace-write"')
    completed = _run_hook(
        hook,
        {
            "hook_event_name": "PreToolUse",
            "agent_type": "kvk-test-reviewer",
            "tool_name": "Edit",
        },
    )
    assert (completed.returncode, completed.stdout) == (0, "")


def test_read_only_hook_limits_only_agents_declared_read_only() -> None:
    """正本で読み取り専用と宣言したAgentだけを制限し、主Sessionと他のAgentは通す。"""

    command = {"command": "touch tmp/readonly-probe.txt"}
    for agent_type in (
        "kvk-architecture-reviewer",
        "kvk-domain-reviewer",
        "kvk-requirements-reviewer",
        "kvk-test-reviewer",
        "evidence-reviewer",
    ):
        payload = {**_tool_payload("Bash", command), "agent_type": agent_type}
        decision = _read_only_decision(payload)
        assert decision is not None and decision[0] == "deny", agent_type

    main_session = _tool_payload("Bash", command)
    del main_session["agent_type"]
    for payload in (
        main_session,
        {**_tool_payload("Bash", command), "agent_type": "general-purpose"},
        {**_tool_payload("Edit", {"file_path": "x"}), "agent_type": "Explore"},
        # パスとして解釈され得る名前で正本外のファイルを読ませない。
        {**_tool_payload("Bash", command), "agent_type": "../agents/kvk-test-reviewer"},
    ):
        assert _read_only_decision(payload) is None, payload


def test_claude_settings_register_repository_hooks() -> None:
    """Claude Codeの共有設定がGit保護と共有記憶のHookを登録する。"""

    settings = json.loads(CLAUDE_SETTINGS_PATH.read_text(encoding="utf-8"))
    hooks = settings["hooks"]

    pre_tool_use = hooks["PreToolUse"]
    matchers = {entry["matcher"] for entry in pre_tool_use}
    assert "Bash|PowerShell" in matchers
    pre_arguments = [hook["args"] for entry in pre_tool_use for hook in entry["hooks"]]
    assert [
        "${CLAUDE_PROJECT_DIR}/tools/hooks/block_dangerous_git.py",
        "--ask-push",
    ] in pre_arguments
    # Subagent定義のHookは発火しないため、共有設定から全Tool呼び出しを検査する。
    read_only_entries = [
        entry
        for entry in pre_tool_use
        if any(
            hook["args"]
            == ["${CLAUDE_PROJECT_DIR}/tools/hooks/enforce_read_only_agent.py"]
            for hook in entry["hooks"]
        )
    ]
    assert len(read_only_entries) == 1
    # 読み取りToolと内部Toolでは起動せず、書き込み得るToolだけを検査する。
    matcher = re.compile(read_only_entries[0]["matcher"])
    for tool_name in (
        "Bash",
        "PowerShell",
        "Monitor",
        "Edit",
        "Write",
        "NotebookEdit",
        "Agent",
        "mcp__example__write",
        "mcp__playwright__browser_navigate",
    ):
        assert matcher.fullmatch(tool_name), tool_name
    for tool_name in (
        "Read",
        "Grep",
        "Glob",
        "WebSearch",
        "WebFetch",
        "SubagentHandback",
        "ToolSearch",
        "TodoWrite",
    ):
        assert not matcher.fullmatch(tool_name), tool_name

    for event, argument in (("SessionStart", "session-start"), ("Stop", "stop")):
        arguments = [hook["args"] for entry in hooks[event] for hook in entry["hooks"]]
        assert [
            "${CLAUDE_PROJECT_DIR}/tools/hooks/project_memory_hook.py",
            argument,
        ] in arguments, event

    # Windowsでもシェルの変数展開へ依存しないよう、exec形式で起動する。
    for entries in hooks.values():
        for entry in entries:
            for hook in entry["hooks"]:
                assert hook["type"] == "command"
                assert hook["command"] == "python"


def test_claude_settings_deny_generated_files_and_secrets() -> None:
    """生成物の直接編集、秘密情報の読み取り、Hookを迂回するToolを権限規則で拒否する。"""

    settings = json.loads(CLAUDE_SETTINGS_PATH.read_text(encoding="utf-8"))
    deny = set(settings["permissions"]["deny"])
    assert {
        "Edit(.claude/skills/**)",
        "Edit(.claude/agents/**)",
        "Read(.env)",
        "Read(.env.*)",
        # Node.jsのプロセスでコードを実行でき、Bash Toolを通るGit保護と`.env`の拒否を迂回する（ADR 0032）。
        "mcp__playwright__browser_run_code_unsafe",
        # 作業ツリーのファイルをページへ渡し、`.env`の読み取りの拒否を迂回する（ADR 0032）。
        "mcp__playwright__browser_drop",
        "mcp__playwright__browser_file_upload",
    } <= deny
    # 同期Scriptと品質ゲートが動かなくならないよう、実行系の規則は加えない。
    assert not any(rule.startswith("Bash(") for rule in deny)


def _browser_file_decision(payload: object) -> tuple[str, str] | None:
    """ブラウザの出力先のHook判定と理由を返す。許可時はNoneを返す。"""

    completed = _run_hook(BROWSER_FILE_SCRIPT, payload)
    assert completed.returncode == 0, completed.stderr
    if completed.stdout == "":
        return None
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    return output["permissionDecision"], output["permissionDecisionReason"]


def _browser_tool(tool_input: object) -> dict[str, object]:
    """主SessionのPlaywright MCPのTool呼び出しを作る。"""

    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "mcp__playwright__browser_evaluate",
        "tool_input": tool_input,
    }


def test_browser_tools_may_write_only_under_their_output_directory() -> None:
    """`filename`を持つToolは、名前の有無にかかわらず`tmp/playwright-mcp/`の外へ書けない。"""

    for tool_input in (
        {},
        {"filename": "tmp/playwright-mcp/page.png"},
        {"filename": "tmp/playwright-mcp/2026/page.yml"},
        {"filename": "tmp/playwright-mcp/画面.png"},
    ):
        assert _browser_file_decision(_browser_tool(tool_input)) is None, tool_input

    for filename in (
        "tools/hooks/block_dangerous_git.py",
        ".claude/settings.json",
        ".git/config",
        "page.png",
        "tmp/page.png",
        "tmp/playwright-mcp",
        "tmp/playwright-mcp/",
        "tmp/playwright-mcp-other/page.png",
        "tmp/playwright-mcp/../../.mcp.json",
        "tmp/playwright-mcp/a/../../page.png",
        "./tmp/playwright-mcp/page.png",
        "tmp//playwright-mcp/page.png",
        "tmp/playwright-mcp/./page.png",
        "tmp/playwright-mcp//page.png",
        "tmp/playwright-mcp/..\\..\\page.png",
        "tmp\\playwright-mcp\\..\\page.png",
        "/workspaces/KvK-Team-Builder/tmp/playwright-mcp/page.png",
        "C:/tmp/playwright-mcp/page.png",
        "tmp/playwright-mcp/C:page.png",
        "",
    ):
        decision = _browser_file_decision(_browser_tool({"filename": filename}))
        assert decision is not None and decision[0] == "deny", filename
        assert "tmp/playwright-mcp/" in decision[1]


def test_browser_tools_may_not_move_the_base_of_filename() -> None:
    """`_meta.cwd`は`filename`の解決の基準を変えるため、値にかかわらず通さない（ADR 0032）。"""

    for meta in ({"cwd": "/workspaces/KvK-Team-Builder/tests"}, {"raw": True}, {}):
        for tool_input in (
            {"filename": "tmp/playwright-mcp/test_x.py", "_meta": meta},
            {"_meta": meta},
        ):
            decision = _browser_file_decision(_browser_tool(tool_input))
            assert decision is not None and decision[0] == "deny", tool_input
            assert "_meta" in decision[1]


def _run_browser_file_hook_with_bytes(
    body: bytes,
) -> subprocess.CompletedProcess[bytes]:
    """既定の文字コードがUTF-8でない環境で、バイト列をそのままHookへ渡す。"""

    return subprocess.run(
        [sys.executable, str(BROWSER_FILE_SCRIPT)],
        input=body,
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252"},
        capture_output=True,
        check=False,
    )


def test_browser_file_hook_reads_utf8_regardless_of_the_console() -> None:
    """日本語の名前をUTF-8のバイト列から読み、拒否のJSONはASCIIで出力する。"""

    def body(filename: str) -> bytes:
        return json.dumps(
            _browser_tool({"filename": filename}), ensure_ascii=False
        ).encode("utf-8")

    allowed = _run_browser_file_hook_with_bytes(body("tmp/playwright-mcp/画面.png"))
    assert (allowed.returncode, allowed.stdout) == (0, b"")

    denied = _run_browser_file_hook_with_bytes(body("画面.png"))
    assert denied.returncode == 0
    assert denied.stdout.isascii()
    output = json.loads(denied.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"


def test_browser_file_hook_denies_unreadable_bytes() -> None:
    """例外で終わるとClaude CodeはToolを通すため、読めない入力も拒否として答える。"""

    depth = 200_000
    for body in (
        b"not json",
        b"\xff\xfe",
        ('{"tool_input":{"x":' + "[" * depth + "]" * depth + "}}").encode("ascii"),
    ):
        completed = _run_browser_file_hook_with_bytes(body)
        assert completed.returncode == 0, body[:20]
        output = json.loads(completed.stdout)["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny", body[:20]


def test_browser_file_hook_denies_input_it_cannot_understand() -> None:
    """安全策のHookは、解析できない入力と型の違う`filename`を通さない。"""

    for payload in (
        ["not", "an", "object"],
        {"tool_name": "mcp__playwright__browser_snapshot"},
        _browser_tool("filename"),
        _browser_tool({"filename": None}),
        _browser_tool({"filename": ["tmp/playwright-mcp/page.png"]}),
    ):
        decision = _browser_file_decision(payload)
        assert decision is not None and decision[0] == "deny", payload


def test_browser_file_hook_is_registered_for_every_session_and_playwright_tool() -> (
    None
):
    """読み取り専用の宣言のToolも含め、主SessionのPlaywright MCPの全Toolを検査する。"""

    settings = json.loads(CLAUDE_SETTINGS_PATH.read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in settings["hooks"]["PreToolUse"]
        if any(
            hook["args"]
            == ["${CLAUDE_PROJECT_DIR}/tools/hooks/restrict_browser_files.py"]
            for hook in entry["hooks"]
        )
    ]
    assert len(entries) == 1
    matcher = re.compile(entries[0]["matcher"])
    for tool_name in (
        "mcp__playwright__browser_evaluate",
        "mcp__playwright__browser_network_request",
        "mcp__playwright__browser_take_screenshot",
    ):
        assert matcher.fullmatch(tool_name), tool_name
    for tool_name in ("Bash", "Read", "mcp__example__write"):
        assert not matcher.fullmatch(tool_name), tool_name


def test_worktree_directories_are_ignored() -> None:
    """Session用worktreeを元の作業ツリーの差分や品質ゲートへ混ぜない。"""

    ignored = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".worktrees/" in ignored
    assert ".claude/worktrees/" in ignored


def _run_git(repository: Path, *arguments: str) -> None:
    """Test用RepositoryでGit Commandを実行する。"""

    subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def _create_memory_repository(tmp_path: Path) -> tuple[Path, Path]:
    """共有記憶ScriptとHookを配置したTest用Repositoryを作る。"""

    repository = tmp_path / "repository"
    script = (
        repository
        / ".agents"
        / "skills"
        / "maintain-project-memory"
        / "scripts"
        / "session_memory.py"
    )
    script.parent.mkdir(parents=True)
    shutil.copy2(PROJECT_MEMORY_SCRIPT, script)
    hook = repository / "tools" / "hooks" / "project_memory_hook.py"
    hook.parent.mkdir(parents=True)
    shutil.copy2(MEMORY_HOOK_SCRIPT, hook)
    memory_root = repository / "docs" / "project-memory"
    memory_root.mkdir(parents=True)
    (memory_root / "README.md").write_text("# Test Memory\n", encoding="utf-8")
    (repository / "feature.txt").write_text("base\n", encoding="utf-8")

    _run_git(repository, "init")
    _run_git(repository, "config", "user.name", "Test User")
    _run_git(repository, "config", "user.email", "test@example.com")
    _run_git(repository, "add", ".")
    _run_git(repository, "commit", "-m", "initial")
    return repository, hook


def test_memory_hook_starts_session_and_reminds_once_before_stop(
    tmp_path: Path,
) -> None:
    """SessionStartで開始状態を保存し、未記録の変更があれば一度だけ停止を止める。"""

    repository, hook = _create_memory_repository(tmp_path)
    session_id = "11111111-2222-3333-4444-555555555555"

    started = _run_hook(
        hook,
        {"hook_event_name": "SessionStart", "session_id": session_id},
        "session-start",
        cwd=repository,
    )
    assert started.returncode == 0, started.stderr
    context = json.loads(started.stdout)["hookSpecificOutput"]
    assert context["hookEventName"] == "SessionStart"
    assert session_id in context["additionalContext"]

    resumed = _run_hook(
        hook,
        {"hook_event_name": "SessionStart", "session_id": session_id},
        "session-start",
        cwd=repository,
    )
    assert resumed.returncode == 0, resumed.stderr
    assert (
        session_id
        in json.loads(resumed.stdout)["hookSpecificOutput"]["additionalContext"]
    )

    stop_payload = {
        "hook_event_name": "Stop",
        "session_id": session_id,
        "stop_hook_active": False,
    }
    unchanged = _run_hook(hook, stop_payload, "stop", cwd=repository)
    assert unchanged.returncode == 0, unchanged.stderr
    assert unchanged.stdout == ""

    (repository / "feature.txt").write_text("Sessionの変更\n", encoding="utf-8")
    blocked = _run_hook(hook, stop_payload, "stop", cwd=repository)
    assert blocked.returncode == 0, blocked.stderr
    decision = json.loads(blocked.stdout)
    assert decision["decision"] == "block"
    assert "feature.txt" in decision["reason"]
    assert session_id in decision["reason"]

    reminded = _run_hook(hook, stop_payload, "stop", cwd=repository)
    assert reminded.returncode == 0, reminded.stderr
    assert reminded.stdout == ""

    active = _run_hook(
        hook, {**stop_payload, "stop_hook_active": True}, "stop", cwd=repository
    )
    assert active.stdout == ""


def test_memory_hook_does_not_block_unknown_sessions(tmp_path: Path) -> None:
    """開始状態のないSessionや壊れた入力では作業を止めない。"""

    repository, hook = _create_memory_repository(tmp_path)
    (repository / "feature.txt").write_text("変更\n", encoding="utf-8")

    unknown = _run_hook(
        hook,
        {"hook_event_name": "Stop", "session_id": "unknown-session"},
        "stop",
        cwd=repository,
    )
    assert unknown.returncode == 0, unknown.stderr
    assert unknown.stdout == ""

    broken = subprocess.run(
        [sys.executable, str(hook), "stop"],
        input="not json",
        cwd=repository,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert broken.returncode == 0
    assert "decision" not in broken.stdout


def test_memory_hook_tells_second_session_to_use_a_worktree(tmp_path: Path) -> None:
    """同じ作業ツリーを別Sessionが使用中なら、SessionStartでworktreeを案内する。"""

    repository, hook = _create_memory_repository(tmp_path)

    first = _run_hook(
        hook,
        {"hook_event_name": "SessionStart", "session_id": "first-session"},
        "session-start",
        cwd=repository,
    )
    assert first.returncode == 0, first.stderr
    first_context = json.loads(first.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "worktree" not in first_context

    second = _run_hook(
        hook,
        {"hook_event_name": "SessionStart", "session_id": "second-session"},
        "session-start",
        cwd=repository,
    )
    assert second.returncode == 0, second.stderr
    second_context = json.loads(second.stdout)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert "worktree" in second_context
    assert "$implement" in second_context
    assert "second-session" in second_context


def test_memory_hook_follows_session_into_a_linked_worktree(tmp_path: Path) -> None:
    """Session用worktreeへ移った後は、そのworktreeの開始状態で記録漏れを確認する。"""

    repository, hook = _create_memory_repository(tmp_path)
    worktree = repository / ".claude" / "worktrees" / "topic"
    _run_git(repository, "worktree", "add", "-b", "topic", str(worktree))
    session_id = "worktree-session"

    started = _run_hook(
        hook,
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id,
            "cwd": str(worktree),
        },
        "session-start",
        cwd=worktree,
    )
    assert started.returncode == 0, started.stderr

    (worktree / "feature.txt").write_text("worktreeの変更\n", encoding="utf-8")
    stop_payload = {
        "hook_event_name": "Stop",
        "session_id": session_id,
        "stop_hook_active": False,
        "cwd": str(worktree),
    }
    blocked = _run_hook(hook, stop_payload, "stop", cwd=worktree)
    assert blocked.returncode == 0, blocked.stderr
    assert json.loads(blocked.stdout)["decision"] == "block"

    # 元の作業ツリーには開始状態を作らない。
    main_stop = _run_hook(
        hook, {**stop_payload, "cwd": str(repository)}, "stop", cwd=repository
    )
    assert main_stop.returncode == 0, main_stop.stderr
    assert main_stop.stdout == ""

    # Repository外のcwdは信用せず、元の作業ツリーとして扱う。
    outside = _run_hook(
        hook, {**stop_payload, "cwd": str(tmp_path)}, "stop", cwd=repository
    )
    assert outside.returncode == 0, outside.stderr
    assert outside.stdout == ""


def test_memory_hook_ignores_virtual_environment_of_another_os(tmp_path: Path) -> None:
    """Windowsと共有するWorkspaceで、別OS用のvenvのPythonを起動しない。"""

    repository, hook = _create_memory_repository(tmp_path)
    other_python = (
        repository / ".venv" / "bin" / "python"
        if os.name == "nt"
        else repository / ".venv" / "Scripts" / "python.exe"
    )
    other_python.parent.mkdir(parents=True)
    other_python.write_bytes(b"MZ not runnable on this OS")

    started = _run_hook(
        hook,
        {"hook_event_name": "SessionStart", "session_id": "shared-venv"},
        "session-start",
        cwd=repository,
    )
    assert started.returncode == 0, started.stderr
    assert "shared-venv" in started.stdout
