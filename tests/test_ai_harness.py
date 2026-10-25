"""CodexとClaude Code向けレビューエージェントと共有スキルの構造テスト。"""

import ast
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from types import ModuleType

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIRECTORY = PROJECT_ROOT / ".codex" / "agents"
SKILL_DIRECTORY = PROJECT_ROOT / ".agents" / "skills"
CODE_REVIEW_AGENTS = {
    "kvk-architecture-reviewer",
    "kvk-domain-reviewer",
    "kvk-requirements-reviewer",
    "kvk-test-reviewer",
}
EVIDENCE_REVIEW_AGENT = "evidence-reviewer"
EXPECTED_AGENTS = CODE_REVIEW_AGENTS | {EVIDENCE_REVIEW_AGENT}
# 判断の重い担当だけ上位のモデルを使う（ADR 0030）。
HEAVY_REVIEW_AGENTS = {
    "kvk-architecture-reviewer",
    "kvk-requirements-reviewer",
    EVIDENCE_REVIEW_AGENT,
}
REVIEW_REPORT_HEADINGS = ("## Must", "## Should", "## Nice", "## 未確定")
EVIDENCE_TABLE_HEADER = "| 主張 | 判定 | 出典URL | 確認日 | 必要な訂正 |"
EXPECTED_PROJECT_SKILLS = {
    "apple-design",
    "change-ai-harness",
    "change-kvk-rules",
    "choose-skill",
    "codex-handoff",
    "create-github-pr",
    "git-guardrails-codex",
    "implement",
    "manage-github-issue",
    "maintain-project-memory",
    "research",
    "review-kvk-change",
}
EXPLICIT_ONLY_PROJECT_SKILLS = {"choose-skill", "codex-handoff", "implement"}
CLAUDE_SKILL_DIRECTORY = PROJECT_ROOT / ".claude" / "skills"
CLAUDE_AGENT_DIRECTORY = PROJECT_ROOT / ".claude" / "agents"
CODEX_ONLY_SKILLS = {"codex-handoff", "git-guardrails-codex"}
SYNC_SCRIPT = PROJECT_ROOT / "tools" / "sync_agent_config.py"
SKILLS_LOCK_PATH = PROJECT_ROOT / "skills-lock.json"
PROJECT_MEMORY_ROOT = PROJECT_ROOT / "docs" / "project-memory"
PROJECT_MEMORY_SCRIPT = (
    SKILL_DIRECTORY / "maintain-project-memory" / "scripts" / "session_memory.py"
)
JAPANESE_TEXT_PATTERN = re.compile(r"[ぁ-んァ-ヶ一-龠々ー]")
REVIEW_LEVELS = ("Must", "Should", "Nice")


def test_review_agents_request_read_only_toml_definitions() -> None:
    """専門Reviewerがread-onlyを要求するProject Agent定義を持つ。"""

    paths = sorted(AGENT_DIRECTORY.glob("*.toml"))
    assert {path.stem for path in paths} == EXPECTED_AGENTS

    for path in paths:
        with path.open("rb") as source:
            definition = tomllib.load(source)
        assert definition["name"] == path.stem
        assert definition["description"]
        assert definition["developer_instructions"]
        assert JAPANESE_TEXT_PATTERN.search(definition["description"])
        assert JAPANESE_TEXT_PATTERN.search(definition["developer_instructions"])
        assert definition["sandbox_mode"] == "read-only"
        assert definition["model_reasoning_effort"] == "high"
        expected_model = (
            "gpt-6.1-sol" if path.stem in HEAVY_REVIEW_AGENTS else "gpt-6-luna"
        )
        assert definition["model"] == expected_model, path.stem


def test_review_agents_return_reports_the_stop_hook_can_check() -> None:
    """SubagentStop Hookが検査する見出しと列を、各Agentの指示が求める。"""

    for name in EXPECTED_AGENTS:
        with (AGENT_DIRECTORY / f"{name}.toml").open("rb") as source:
            instructions = tomllib.load(source)["developer_instructions"]
        if name == EVIDENCE_REVIEW_AGENT:
            assert EVIDENCE_TABLE_HEADER in instructions
            continue
        for heading in REVIEW_REPORT_HEADINGS:
            assert f"`{heading}`" in instructions, (name, heading)
        assert "「なし」" in instructions, name


def test_review_skill_checks_enforcement_and_incomplete_reports() -> None:
    """強制を確かめてから委譲し、不完全な結果の観点を主エージェントが確認し直す。"""

    source = _compact(
        (SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md").read_text(encoding="utf-8")
    )
    for required in (
        "SessionStartHookのContextが届いていれば動いているとみなす",
        "`/hooks`で`.codex/hooks.json`のHookを信頼済みか尋ね",
        "確かめられなければ、読み取り専用の強制を適用できない場合として扱う",
        "起動時に`model`を指定しない",
        "報告を返さずに止まった担当には、追加の調査をせず確かめた内容で報告をまとめるよう続きを指示する",
        "不完全な結果とみなす",
        "「前提と未実行の検査」に書く",
    ):
        assert _compact(required) in source, required

    # 証拠担当の打ち切られた判定表を、検証済みとして扱わない。
    research = _compact(
        (SKILL_DIRECTORY / "research" / "SKILL.md").read_text(encoding="utf-8")
    )
    for required in (
        "一部の主張にしか判定がない結果は、打ち切られた不完全な結果とみなす",
        "独立に検証できなかった主張として報告する",
        # Subagentは利用者に尋ねられないため、主Agentが強制を確かめて結果を渡す。
        "主Agentが起動の前に、`$review-kvk-change`の「独立した観点を委譲する」と同じ方法で",
        "確かめた結果（動いている、または確かめられない）を、問いと一緒にSubagentへ渡す",
        "動いていると渡された場合だけ起動し、それ以外（確かめられない、または渡されていない）は"
        "起動できない環境として扱う",
        "起動時に`model`を指定しない",
        "追加の調査をせず確かめた内容で報告をまとめるよう続きを指示する",
    ):
        assert _compact(required) in research, required
    # 利用者の直接起動では確認の結果が渡らないため、独立検証しないことを明示する。
    for required in (
        "利用者が`/research`で直接起動した場合は確認の結果が渡らないため",
        "独立検証が要る調査は主Sessionに依頼する",
    ):
        assert _compact(required) in research, required
    research_description = _frontmatter(SKILL_DIRECTORY / "research" / "SKILL.md")[
        "description"
    ]
    assert "読み取り専用の強制を確かめた結果" in research_description

    # Claude Codeの主Sessionは、確かめた結果をSkill Toolの`args`へ渡す。
    claude_policy = _compact((PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8"))
    for required in (
        "起動の前に主Sessionが確かめた読み取り専用の強制の結果",
        "利用者が`/research`で直接起動した場合は",
    ):
        assert _compact(required) in claude_policy, required

    # CodexではGit保護Hookがpushを拒否するため、利用者に頼んでpush済みを確かめる。
    for skill_name, required in (
        ("create-github-pr", "pushせずに同じコマンドを利用者に示して実行を頼む"),
        ("create-github-pr", "`git ls-remote --heads origin <branch>`"),
        ("implement", "利用者にpushを頼み、push済みを確かめてから続ける"),
    ):
        skill_source = _compact(
            (SKILL_DIRECTORY / skill_name / "SKILL.md").read_text(encoding="utf-8")
        )
        assert _compact(required) in skill_source, (skill_name, required)
    assert "pushは利用者に頼みます" in (PROJECT_ROOT / "AGENTS.md").read_text(
        encoding="utf-8"
    )

    guardrail = (SKILL_DIRECTORY / "git-guardrails-codex" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    # 追跡する`.codex/hooks.json`へ個人の設定を混ぜない。
    assert (
        "`.codex/hooks.json`へScriptのコピーや相対パスのHookを追記しない" in guardrail
    )
    assert "python3 .codex/hooks/" not in guardrail
    assert "ADR 0030" in guardrail


def test_review_harness_uses_human_decision_levels() -> None:
    """Review結果を人間が判断できる3段階へ統一する。"""

    skill_source = (SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "承認" in skill_source
    assert "P0" not in skill_source
    for decision in ("承認不可", "要判断", "承認候補"):
        assert decision in skill_source

    agents_policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for level in REVIEW_LEVELS:
        assert f"`{level}`" in skill_source
        assert f"`{level}`" in agents_policy

    for name in sorted(CODE_REVIEW_AGENTS):
        with (AGENT_DIRECTORY / f"{name}.toml").open("rb") as source:
            instructions = tomllib.load(source)["developer_instructions"]
        assert "P0〜P3" not in instructions
        for level in REVIEW_LEVELS:
            assert level in instructions


def test_shared_skills_have_valid_metadata_without_placeholders() -> None:
    """共有Skillの発見情報とUIメタデータを版管理する。"""

    paths = sorted(SKILL_DIRECTORY.glob("*/SKILL.md"))
    skills_lock = json.loads(SKILLS_LOCK_PATH.read_text(encoding="utf-8"))
    installed_skills = skills_lock["skills"]
    assert {path.parent.name for path in paths} == (
        EXPECTED_PROJECT_SKILLS | set(installed_skills)
    )

    for path in paths:
        skill_name = path.parent.name
        source = path.read_text(encoding="utf-8")
        assert source.startswith("---\n")

        _, frontmatter_source, body = source.split("---", maxsplit=2)
        frontmatter = yaml.safe_load(frontmatter_source)
        assert {"name", "description"} <= set(frontmatter)
        assert frontmatter["name"] == skill_name
        assert isinstance(frontmatter["description"], str)
        assert frontmatter["description"].strip()
        assert body.strip()

        metadata_path = path.parent / "agents" / "openai.yaml"
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        assert "interface" in metadata
        interface = metadata["interface"]
        assert interface["display_name"]
        assert interface["short_description"]

        if skill_name in EXPECTED_PROJECT_SKILLS:
            assert "TODO" not in source
            assert set(frontmatter) == {"name", "description"}
            assert JAPANESE_TEXT_PATTERN.search(frontmatter["description"])
            assert JAPANESE_TEXT_PATTERN.search(body)
            expected_metadata = (
                {"interface", "policy"}
                if skill_name in (EXPLICIT_ONLY_PROJECT_SKILLS)
                else {"interface"}
            )
            assert set(metadata) == expected_metadata
            if skill_name in EXPLICIT_ONLY_PROJECT_SKILLS:
                assert metadata["policy"] == {"allow_implicit_invocation": False}
            assert f"${skill_name}" in interface["default_prompt"]
            assert JAPANESE_TEXT_PATTERN.search(interface["display_name"])
            assert JAPANESE_TEXT_PATTERN.search(interface["short_description"])
            assert JAPANESE_TEXT_PATTERN.search(interface["default_prompt"])
            continue

        lock_entry = installed_skills[skill_name]
        assert lock_entry["source"] == "mattpocock/skills"
        assert lock_entry["sourceType"] == "github"
        assert lock_entry["skillPath"].endswith(f"/{skill_name}/SKILL.md")
        assert re.fullmatch(r"[0-9a-f]{64}", lock_entry["computedHash"])


def test_codex_native_skills_replace_claude_specific_workflows() -> None:
    """Codex向けSkillがClaude固有の実行方法へ依存しない。"""

    skills_lock = json.loads(SKILLS_LOCK_PATH.read_text(encoding="utf-8"))["skills"]
    for removed_skill in (
        "ask-matt",
        "claude-handoff",
        "git-guardrails-claude-code",
    ):
        assert removed_skill not in skills_lock
        assert not (SKILL_DIRECTORY / removed_skill).exists()

    router_source = (SKILL_DIRECTORY / "choose-skill" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "$change-kvk-rules",
        "$review-kvk-change",
        "$create-github-pr",
        "$manage-github-issue",
    ):
        assert required in router_source

    handoff_source = (SKILL_DIRECTORY / "codex-handoff" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Subagent" in handoff_source
    assert "claude --bg" not in handoff_source

    guardrail_source = (
        SKILL_DIRECTORY / "git-guardrails-codex" / "SKILL.md"
    ).read_text(encoding="utf-8")
    for required in (
        ".codex/hooks.json",
        "PreToolUse",
        "commandWindows",
        "tools/hooks/block_dangerous_git.py",
    ):
        assert required in guardrail_source
    assert ".claude" not in guardrail_source
    assert not (SKILL_DIRECTORY / "git-guardrails-codex" / "scripts").exists()


def test_repository_does_not_ship_skills_for_other_ecosystems() -> None:
    """Python Repositoryで使わないTypeScript／JavaScript向けSkillを配布しない。"""

    skills_lock = json.loads(SKILLS_LOCK_PATH.read_text(encoding="utf-8"))["skills"]
    for removed_skill in (
        "migrate-to-shoehorn",
        "scaffold-exercises",
        "setup-pre-commit",
        "setup-ts-deep-modules",
    ):
        assert removed_skill not in skills_lock
        assert not (SKILL_DIRECTORY / removed_skill).exists()
        assert not (CLAUDE_SKILL_DIRECTORY / removed_skill).exists()


def test_ai_harness_changes_have_a_repository_procedure() -> None:
    """AIハーネスの変更手順を昇格先のSkillと規約で一貫させる。"""

    skill_directory = SKILL_DIRECTORY / "change-ai-harness"
    source = (skill_directory / "SKILL.md").read_text(encoding="utf-8")
    for required in (
        "skills-lock.json",
        "tests/test_ai_harness.py",
        "python tools/sync_agent_config.py",
        "python tools/check.py",
        "tools/hooks/",
        "docs/adr/",
        "references/checklist.md",
    ):
        assert required in source
    assert (skill_directory / "references" / "checklist.md").is_file()

    for path in (
        PROJECT_ROOT / "AGENTS.md",
        SKILL_DIRECTORY / "choose-skill" / "SKILL.md",
    ):
        assert "$change-ai-harness" in path.read_text(encoding="utf-8")

    agents_policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "tests/test_tool_output_encoding.py" in agents_policy
    assert "UTF-8" in agents_policy

    for candidate, promoted_to in (
        ("ai-harness-change-procedure", ".agents/skills/change-ai-harness/SKILL.md"),
        ("windows-utf8-tool-io", "AGENTS.md"),
    ):
        metadata = _frontmatter(PROJECT_MEMORY_ROOT / "candidates" / f"{candidate}.md")
        assert metadata["status"] == "promoted"
        assert metadata["promoted_to"] == promoted_to
        assert (PROJECT_ROOT / promoted_to).is_file()


def test_implement_skill_follows_repository_completion_rules() -> None:
    """実装Skillが規約と矛盾せず、完了条件と再開手順を持つ。"""

    skills_lock = json.loads(SKILLS_LOCK_PATH.read_text(encoding="utf-8"))["skills"]
    assert "implement" not in skills_lock
    source = (SKILL_DIRECTORY / "implement" / "SKILL.md").read_text(encoding="utf-8")
    for required in (
        "$maintain-project-memory",
        "$change-kvk-rules",
        "$tdd",
        "$review-kvk-change",
        "python tools/check.py",
        "python tools/preview_output.py",
        "tmp/progress/",
        "完了条件",
    ):
        assert required in source
    assert "/code-review" not in source
    assert "Commit your work" not in source
    assert "利用者が明示" in source

    rules_source = (SKILL_DIRECTORY / "change-kvk-rules" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "python tools/preview_output.py" in rules_source


def test_github_pr_skill_guards_credentials_and_external_actions() -> None:
    """PR作成Skillが認証情報と外部作用を安全に扱う。"""

    skill_source = (SKILL_DIRECTORY / "create-github-pr" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    agents_policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    development_guide = (PROJECT_ROOT / "DEVELOPMENT.md").read_text(encoding="utf-8")
    pull_request_template = (
        PROJECT_ROOT / ".github" / "pull_request_template.md"
    ).read_text(encoding="utf-8")

    for required in (
        "gh auth status --active --hostname github.com",
        "gh api user --jq .login",
        "gh pr list",
        "gh pr create",
        "--body-file",
        "python tools/check.py",
        "明示的な依頼",
        "既存のopen Pull Request",
    ):
        assert required in skill_source

    credential_guard = next(
        paragraph
        for paragraph in skill_source.split("\n\n")
        if "gh auth token" in paragraph
    )
    assert "行わない" in credential_guard
    assert "--show-token" in credential_guard
    assert ".env" in skill_source
    assert "force push" in skill_source
    assert "$create-github-pr" in agents_policy
    assert "$create-github-pr" in development_guide
    for heading in ("## 関連情報", "## 確認結果"):
        assert heading in pull_request_template


def test_branching_flows_work_branches_through_dev_to_main() -> None:
    """作業branchはdevへ、devだけがmainへmerge commitで取り込まれる運用を規約とSkillが共有する。"""

    agents_policy = _compact((PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    for required in (
        "##ブランチ運用",
        "作業branchは`dev`から作り、`dev`へのPullRequestで取り込む",
        "`origin/dev`から作る",
        "`main`へ取り込むのは`dev`からのPullRequestだけとし、mergecommitで取り込む",
        "squashやrebaseで取り込まない",
        "緊急の修正も`dev`を経由する",
        "`main`と`dev`へ直接コミットまたはpushしない",
        "導入時に`main`から`dev`を作る最初の通常pushだけを例外とする",
        "リリースPullRequestのレビューは毎回初回のレビューとして扱い",
        "前回のリリースの指摘、見送り、振り返りの回数を引き継がない",
        "ADR0027",
    ):
        assert required in agents_policy, required

    pr_skill = _compact(
        (SKILL_DIRECTORY / "create-github-pr" / "SKILL.md").read_text(encoding="utf-8")
    )
    for required in (
        "baseを省略した場合、作業branchでは`dev`、`dev`では`main`とする",
        "`dev`以外のbranchから`main`へのPullRequestと、`main`をheadにしたPullRequestは、"
        "利用者が指定しても作らず",
        "`gitfetchorigin<base>`が失敗する場合",
        "コミット一覧は`origin/<base>..HEAD`、差分は`origin/<base>...HEAD`で収集し",
        "`HEAD`と`origin/dev`が同じコミットであることを確かめ、違えば止める",
        "headが`dev`の場合はpushせず",
        # 起点を追跡したbranchはupstreamがあるように見え、pushを飛ばして`dev`を指してしまう。
        "upstreamが`origin/<branch>`でなければ、upstreamがないものとして扱う",
    ):
        assert required in pr_skill, required

    implement_skill = _compact(
        (SKILL_DIRECTORY / "implement" / "SKILL.md").read_text(encoding="utf-8")
    )
    for required in (
        "現在のbranchが`main`か`dev`なら",
        "`gitswitch--no-track-c<branch名>origin/dev`",
        "未コミットの変更があるか、`gitfetchorigindev`が失敗するか、`origin/dev`がなければ、"
        "移らずに利用者へ確認する",
        # 開始時のHEADを基準にすると、`dev`の未リリースの変更が自分の差分になる。
        "同じsession_idで`discard`と`start`をやり直す",
        "gitworktreeadd--no-track-b<branch名>",
        "末尾の`HEAD`を`origin/dev`に替える",
        "ADR0027",
    ):
        assert required in implement_skill, required

    claude_guide = _compact((PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8"))
    for required in (
        "`$implement`の「Session用worktreeへ移る」の手順2で選んだコミット",
        "ただし`$implement`の開始手順2で分岐元を移った場合は",
        "`gitswitch--no-track-C<現在のbranch名><選んだコミット>`",
        "変更があるか、分岐元が`origin/dev`のときにfetchが失敗するか`origin/dev`がなければ、"
        "利用者へ確認する",
        "同じsession_idで`discard`と`start`をやり直す",
        "ADR0027",
    ):
        assert required in claude_guide, required

    development_guide = _compact(
        (PROJECT_ROOT / "DEVELOPMENT.md").read_text(encoding="utf-8")
    )
    for required in (
        "##ブランチ運用",
        "`gitbranch--no-trackdevorigin/main`",
        "「Requireapprovals」は有効にしない",
        "forcepushと削除を許可しない",
        "「Donotallowbypassingtheabovesettings」を有効にし",
        "「Pullrequesttitle」にする",
        "最初のリリースPullRequestで`main`へ出した後に",
        # 有効にすると、2回目以降のリリースやmergecommitが止まる。
        "「Requirebranchestobeuptodatebeforemerging」は有効にしない",
        "「Requirelinearhistory」は有効にしない",
        "`gitremoteset-headorigin--auto`",
        "手順2と手順3は、最初のリリースPullRequestを取り込む前に済ませます",
    ):
        assert required in development_guide, required
    # 保護規則とmerge方式を先に設定しないと、最初のリリースがsquashや英語のmergecommitで入る。
    default_branch_change = development_guide.index(
        "最初のリリースPullRequestで`main`へ出した後に"
    )
    assert development_guide.index("「Requireapprovals」は有効にしない") < (
        default_branch_change
    )
    assert development_guide.index("「Pullrequesttitle」にする") < default_branch_change

    # 必須チェック名はCIのjob名と一致しないと選べないため、matrixから組み立てて照合する。
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8"
    )
    assert "name: ${{ matrix.os }} / Python ${{ matrix.python-version }}" in workflow
    matrix = yaml.safe_load(workflow)["jobs"]["check"]["strategy"]["matrix"]
    assert set(matrix) == {"os", "python-version"}
    expected_checks = {
        f"{operating_system}/Python{version}"
        for operating_system in matrix["os"]
        for version in matrix["python-version"]
    }
    # matrixから外したjobの名前が残ると、走らない必須チェックを待ち続けて取り込めなくなる。
    documented_checks = set(
        re.findall(r"`([a-z]+-latest/Python[0-9.]+)`", development_guide)
    )
    assert documented_checks == expected_checks

    readme = _compact((PROJECT_ROOT / "README.md").read_text(encoding="utf-8"))
    assert "運用では`main`" in readme

    adr = _compact(
        (
            PROJECT_ROOT / "docs" / "adr" / "0027-separate-dev-and-main-branches.md"
        ).read_text(encoding="utf-8")
    )
    for required in (
        "`dev`のコミットをすべて`main`の祖先に含め",
        "「Requirebranchestobeuptodatebeforemerging」と「Requirelinearhistory」は有効にしない",
        "`--no-track`",
        "`$implement`の「Session用worktreeへ移る」の手順2で選んだコミット",
    ):
        assert required in adr, required
    # 出典にない判断ごとに、覆せる仮定であることを示す。
    assert adr.count("（作成者の仮定）") >= 4
    adr_index = (PROJECT_ROOT / "docs" / "adr" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "`0027`" in adr_index


def test_ci_runs_once_per_change_and_cancels_only_stale_pull_requests() -> None:
    """CIは作業branchのpushとPull Requestで重複せず、pushの実行を中止しない。"""

    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
    )
    # YAML 1.1では`on`キーが真偽値として読まれる。
    triggers = workflow[True]
    # pull_request_targetなどを足すと、重複実行やforkへの権限の拡大が戻る。
    assert set(triggers) == {"push", "pull_request"}
    # 作業branchのpushまで対象にすると、Pull Requestと同じjobが2回走る。
    assert triggers["push"] == {"branches": ["main", "dev"]}
    # 対象branchを絞ると、devへのPull RequestかリリースPull Requestの一方が検証されない。
    assert triggers["pull_request"] is None
    # branch名ではforkや同じ名前のbranchのPull Requestとグループが重なるため、番号で分ける。
    # 番号がないpushはrun_idで一意になり、待機中の実行も中止されない。
    assert workflow["concurrency"] == {
        "group": (
            "${{ github.workflow }}-"
            "${{ github.event.pull_request.number || github.run_id }}"
        ),
        "cancel-in-progress": True,
    }

    development_guide = _compact(
        (PROJECT_ROOT / "DEVELOPMENT.md").read_text(encoding="utf-8")
    )
    for required in (
        "CIは`main`と`dev`へのpushと、すべてのPullRequestで実行します",
        "PullRequestを作る前の作業branchのpushでは実行しない",
        "同じPullRequestへ続けてpushすると、古い実行は中止されます",
        "ほかのPullRequestやpushの実行は中止されません",
        # 取り込んだ後のmainへのpushも、devの先頭と同じ内容を検証する。
        "`dev`へのpush、リリースPullRequest、取り込んだ後の`main`へのpushは同じ内容を"
        "検証するため、リリースごとに3回実行されます",
        "（作成者の仮定）PullRequestを作る前にCIで確かめたい場合は、利用者が明示したときに"
        "`$create-github-pr`でDraftPullRequestを作ります",
    ):
        assert required in development_guide, required

    adr = _compact(
        (PROJECT_ROOT / "docs" / "adr" / "0028-run-ci-once-per-change.md").read_text(
            encoding="utf-8"
        )
    )
    for required in (
        "`dev`へのpush、リリースPullRequest、取り込んだ後の`main`へのpushは同じ内容を"
        "検証するため、リリースごとに3回実行される",
        "`dev`へのpushとリリースPullRequestは`dev`の同じ先頭コミットに対して実行される",
        "${{github.event.pull_request.number||github.run_id}}",
        "forkや同じ名前のbranchから出たPullRequestの実行を中止しない",
        "（作成者の仮定）PullRequestを作る前は手元の`pythontools/check.py`で確かめる",
        "利用者が明示したときに`$create-github-pr`でDraftPullRequestを作る",
    ):
        assert required in adr, required
    # 置き換えた文の位置でも、古い判断として読まれないようにする（ADR 0021の前例）。
    replaced_adr = _compact(
        (
            PROJECT_ROOT / "docs" / "adr" / "0027-separate-dev-and-main-branches.md"
        ).read_text(encoding="utf-8")
    )
    for required in (
        "状態:提案中（一部をADR0028で置き換え）",
        "すべてのpushとPullRequestで実行する（ADR0028で置き換えた）",
    ):
        assert required in replaced_adr, required
    adr_index = (PROJECT_ROOT / "docs" / "adr" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "`0028`" in adr_index


def test_github_issue_skill_guards_creation_and_permanent_deletion() -> None:
    """Issue管理Skillが重複作成と誤削除を防ぐ。"""

    skill_source = (SKILL_DIRECTORY / "manage-github-issue" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    agents_policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    development_guide = (PROJECT_ROOT / "DEVELOPMENT.md").read_text(encoding="utf-8")

    for required in (
        "gh auth status --active --hostname github.com",
        "gh api user --jq .login",
        "gh issue list",
        "gh issue create",
        "gh issue view",
        "gh issue delete",
        "--body-file",
        "--yes",
        "pull_request",
        "再承認",
        "復元できない",
        "一括操作",
    ):
        assert required in skill_source

    credential_guard = next(
        paragraph
        for paragraph in skill_source.split("\n\n")
        if "gh auth token" in paragraph
    )
    assert "行わない" in credential_guard
    assert "--show-token" in credential_guard
    assert ".env" in skill_source
    assert "最初の削除依頼を再承認として扱わない" in skill_source
    assert "再承認の直後" in skill_source
    assert "コメント本文は取得しない" in skill_source
    assert "$manage-github-issue" in agents_policy
    assert "$manage-github-issue" in development_guide


def test_github_skills_share_token_scope_policy() -> None:
    """GitHub操作SkillがADR 0008の認証方式、スコープ上限、有効期限に従う。"""

    adr = (
        PROJECT_ROOT / "docs" / "adr" / "0008-codespaces-github-pr-authentication.md"
    ).read_text(encoding="utf-8")
    agents_policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for required in (
        "classic PAT",
        "gh auth login --web",
        "`repo`、`project`、`read:org`、`workflow`",
        "有効期限",
        "delete_repo",
    ):
        assert required in adr
    assert "ADR 0008" in agents_policy

    for skill in ("create-github-pr", "manage-github-issue"):
        skill_source = (SKILL_DIRECTORY / skill / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "ADR 0008" in skill_source
        assert "hosts.yml" in skill_source
        assert "Token scopes" in skill_source

    issue_skill = (SKILL_DIRECTORY / "manage-github-issue" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for required in ("Sub-issue", "Hierarchy", "Epic", "Child"):
        assert required in issue_skill


def test_github_issue_forms_collect_actionable_information_safely() -> None:
    """Issue Formsが再現・受け入れ条件と秘密情報確認を要求する。"""

    template_directory = PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE"
    template_paths = {
        path.name: path for path in sorted(template_directory.glob("*.yml"))
    }
    assert set(template_paths) == {"bug_report.yml", "feature_request.yml"}

    forms = {
        name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, path in template_paths.items()
    }
    for form in forms.values():
        assert set(form) == {"name", "description", "title", "body"}
        assert JAPANESE_TEXT_PATTERN.search(form["name"])
        assert JAPANESE_TEXT_PATTERN.search(form["description"])
        assert form["body"]
        assert "labels" not in form
        assert "assignees" not in form

        fields_by_id = {field["id"]: field for field in form["body"] if "id" in field}
        for field_id in ("duplicate-check", "sensitive-data-check"):
            options = fields_by_id[field_id]["attributes"]["options"]
            assert options
            assert all(option["required"] is True for option in options)

    bug_fields = {
        field["id"]: field for field in forms["bug_report.yml"]["body"] if "id" in field
    }
    for field_id in (
        "summary",
        "reproduction",
        "expected-behavior",
        "actual-behavior",
        "environment",
    ):
        assert bug_fields[field_id]["validations"]["required"] is True

    feature_fields = {
        field["id"]: field
        for field in forms["feature_request.yml"]["body"]
        if "id" in field
    }
    for field_id in ("problem", "desired-outcome", "affected-area"):
        assert feature_fields[field_id]["validations"]["required"] is True


def test_apple_design_is_a_repository_ui_standard() -> None:
    """Web UI変更でapple-designを使うRepository規約を保持する。"""

    agents_policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    architecture = (PROJECT_ROOT / "docs" / "architecture.md").read_text(
        encoding="utf-8"
    )
    skill_directory = SKILL_DIRECTORY / "apple-design"

    assert "$apple-design" in agents_policy
    assert ".agents/skills/apple-design/SKILL.md" in architecture
    assert (skill_directory / "LICENSE").is_file()


def test_project_memory_is_a_repository_policy_and_is_valid() -> None:
    """変更Sessionの共有記憶をRepository規約とScriptで検証する。"""

    agents_policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    development_guide = (PROJECT_ROOT / "DEVELOPMENT.md").read_text(encoding="utf-8")

    assert "$maintain-project-memory" in agents_policy
    assert "$maintain-project-memory" in development_guide
    assert (PROJECT_MEMORY_ROOT / "README.md").is_file()
    assert (PROJECT_MEMORY_ROOT / "INDEX.md").is_file()
    assert PROJECT_MEMORY_SCRIPT.is_file()

    completed = subprocess.run(
        [sys.executable, str(PROJECT_MEMORY_SCRIPT), "validate"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def _run_git(repository: Path, *arguments: str) -> None:
    """Test用RepositoryでGit Commandを実行する。"""

    subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def _run_memory_script(repository: Path, *arguments: str) -> dict[str, object]:
    """Test用共有記憶Scriptを実行し、JSON結果を返す。"""

    script = (
        repository
        / ".agents"
        / "skills"
        / "maintain-project-memory"
        / "scripts"
        / "session_memory.py"
    )
    completed = subprocess.run(
        [sys.executable, str(script), *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert isinstance(result, dict)
    return result


def test_project_memory_records_only_changes_after_session_start(
    tmp_path: Path,
) -> None:
    """開始前の利用者差分を除外し、Session中の変更だけを記憶する。"""

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
    memory_root = repository / "docs" / "project-memory"
    memory_root.mkdir(parents=True)
    (memory_root / "README.md").write_text("# Test Memory\n", encoding="utf-8")
    existing = repository / "existing.txt"
    existing.write_text("base\n", encoding="utf-8")
    feature = repository / "feature.txt"
    feature.write_text("base\n", encoding="utf-8")

    _run_git(repository, "init")
    _run_git(repository, "config", "user.name", "Test User")
    _run_git(repository, "config", "user.email", "test@example.com")
    _run_git(repository, "add", ".")
    _run_git(repository, "commit", "-m", "initial")

    existing.write_text("利用者の既存差分\n", encoding="utf-8")
    started = _run_memory_script(repository, "start")
    session_id = started["session_id"]
    assert isinstance(session_id, str)

    feature.write_text("Sessionで実装した変更\n", encoding="utf-8")
    _run_git(repository, "add", "existing.txt")
    _run_git(repository, "commit", "-m", "commit preexisting user change")
    finished = _run_memory_script(
        repository,
        "finish",
        "--session-id",
        session_id,
        "--slug",
        "feature-change",
        "--title",
        "機能変更を記録",
        "--request",
        "機能を変更する",
        "--outcome",
        "機能ファイルを更新した",
        "--verification",
        "対象Test: 成功",
        "--tag",
        "feature",
    )

    assert finished["recorded"] is True
    assert finished["changed_paths"] == ["feature.txt"]
    memory_path = repository / str(finished["path"])
    metadata_source = memory_path.read_text(encoding="utf-8").split("---", 2)[1]
    metadata = yaml.safe_load(metadata_source)
    assert metadata["related_paths"] == ["feature.txt"]
    assert "existing.txt" not in metadata["related_paths"]
    assert "機能変更を記録" in (memory_root / "INDEX.md").read_text(encoding="utf-8")

    no_change_start = _run_memory_script(repository, "start")
    no_change_session_id = no_change_start["session_id"]
    assert isinstance(no_change_session_id, str)
    no_change = _run_memory_script(
        repository,
        "finish",
        "--session-id",
        no_change_session_id,
        "--slug",
        "no-change",
        "--title",
        "変更なし",
        "--request",
        "状態を確認する",
        "--outcome",
        "変更なし",
    )
    assert no_change == {
        "recorded": False,
        "reason": "セッションによる有効なRepository変更がありません。",
        "changed_paths": [],
    }


def _create_memory_repository(tmp_path: Path) -> Path:
    """共有記憶Scriptだけを配置したTest用Repositoryを作る。"""

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
    memory_root = repository / "docs" / "project-memory"
    memory_root.mkdir(parents=True)
    (memory_root / "README.md").write_text("# Test Memory\n", encoding="utf-8")
    (repository / "feature.txt").write_text("base\n", encoding="utf-8")
    _run_git(repository, "init")
    _run_git(repository, "config", "user.name", "Test User")
    _run_git(repository, "config", "user.email", "test@example.com")
    _run_git(repository, "add", ".")
    _run_git(repository, "commit", "-m", "initial")
    return repository


def test_project_memory_status_reports_pending_changes_once(tmp_path: Path) -> None:
    """statusは未記録の変更を返し、催促済みかどうかを一度だけ切り替える。"""

    repository = _create_memory_repository(tmp_path)

    unknown = _run_memory_script(repository, "status", "--session-id", "unknown")
    assert unknown == {"started": False, "pending_paths": [], "reminded": False}

    started = _run_memory_script(repository, "start", "--session-id", "hook-session")
    assert started["resumed"] is False
    resumed = _run_memory_script(
        repository, "start", "--session-id", "hook-session", "--keep-existing"
    )
    assert resumed["resumed"] is True
    assert resumed["started_at"] == started["started_at"]

    clean = _run_memory_script(
        repository, "status", "--session-id", "hook-session", "--mark-reminded"
    )
    assert clean == {"started": True, "pending_paths": [], "reminded": False}

    (repository / "feature.txt").write_text("変更\n", encoding="utf-8")
    first = _run_memory_script(
        repository, "status", "--session-id", "hook-session", "--mark-reminded"
    )
    assert first == {
        "started": True,
        "pending_paths": ["feature.txt"],
        "reminded": False,
    }
    second = _run_memory_script(
        repository, "status", "--session-id", "hook-session", "--mark-reminded"
    )
    assert second["reminded"] is True


def test_project_memory_suggests_promotion_for_repeated_tags(tmp_path: Path) -> None:
    """同じタグの記憶が3件そろったら昇格候補の検討を促す。"""

    repository = _create_memory_repository(tmp_path)

    results = []
    for number in range(3):
        session = _run_memory_script(repository, "start")
        (repository / "feature.txt").write_text(f"変更{number}\n", encoding="utf-8")
        results.append(
            _run_memory_script(
                repository,
                "finish",
                "--session-id",
                str(session["session_id"]),
                "--slug",
                f"change-{number}",
                "--title",
                f"変更{number}",
                "--request",
                "変更する",
                "--outcome",
                "変更した",
                "--tag",
                "solver-tuning",
            )
        )

    assert results[0]["promotion_hints"] == []
    assert results[1]["promotion_hints"] == []
    hints = results[2]["promotion_hints"]
    assert isinstance(hints, list) and len(hints) == 1
    assert hints[0]["tag"] == "solver-tuning"
    assert len(hints[0]["memory_ids"]) == 3


def _state_file(repository: Path, session_id: str) -> Path:
    """Test用Repositoryの開始状態ファイルを返す。"""

    repository_key = hashlib.sha256(str(repository.resolve()).encode()).hexdigest()[:16]
    return (
        Path(tempfile.gettempdir())
        / "kvk-team-builder-memory"
        / repository_key
        / f"{session_id}.json"
    )


def test_project_memory_detects_other_sessions_in_the_same_worktree(
    tmp_path: Path,
) -> None:
    """別Sessionが同じ作業ツリーを使用中なら、worktreeでの作業を求める。"""

    repository = _create_memory_repository(tmp_path)

    first = _run_memory_script(repository, "start", "--session-id", "first")
    assert first["other_active_sessions"] == []
    assert first["use_separate_worktree"] is False

    second = _run_memory_script(repository, "start", "--session-id", "second")
    assert second["use_separate_worktree"] is True
    others = second["other_active_sessions"]
    assert isinstance(others, list)
    assert [session["session_id"] for session in others] == ["first"]

    # 自分自身の再開は別Sessionとして数えない。
    resumed = _run_memory_script(
        repository, "start", "--session-id", "first", "--keep-existing"
    )
    assert [session["session_id"] for session in resumed["other_active_sessions"]] == [
        "second"
    ]

    # 最後の操作から一定時間が過ぎた開始状態は、終了済みとみなす。
    state_path = _state_file(repository, "first")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["last_seen_at"] = "2000-01-01T00:00:00Z"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    third = _run_memory_script(repository, "start", "--session-id", "third")
    assert [session["session_id"] for session in third["other_active_sessions"]] == [
        "second"
    ]

    # statusは操作の記録を更新し、再び使用中として扱われる。
    _run_memory_script(repository, "status", "--session-id", "first")
    fourth = _run_memory_script(repository, "start", "--session-id", "fourth")
    assert {session["session_id"] for session in fourth["other_active_sessions"]} == {
        "first",
        "second",
        "third",
    }


def test_project_memory_discards_state_without_recording(tmp_path: Path) -> None:
    """worktreeへ移るSessionは、元の作業ツリーの開始状態を記録せずに破棄できる。"""

    repository = _create_memory_repository(tmp_path)
    _run_memory_script(repository, "start", "--session-id", "moving")
    # 別Sessionの変更が元の作業ツリーにあっても、記憶へ取り込まない。
    (repository / "feature.txt").write_text("別Sessionの変更\n", encoding="utf-8")

    discarded = _run_memory_script(repository, "discard", "--session-id", "moving")
    assert discarded == {"discarded": True}
    assert not _state_file(repository, "moving").exists()
    assert list((repository / "docs" / "project-memory").glob("sessions/**/*.md")) == []

    again = _run_memory_script(repository, "discard", "--session-id", "moving")
    assert again == {"discarded": False}


def test_research_skill_records_verdicts_and_check_dates() -> None:
    """調査Skillが主張ごとの判定、出典、確認日を残すRepository固有Skillである。"""

    skills_lock = json.loads(SKILLS_LOCK_PATH.read_text(encoding="utf-8"))["skills"]
    assert "research" not in skills_lock
    source = (SKILL_DIRECTORY / "research" / "SKILL.md").read_text(encoding="utf-8")
    for required in (
        "一次情報",
        "`verified`",
        "`incorrect`",
        "`unresolved`",
        "確認日",
        "発表日",
        "提供開始日",
    ):
        assert required in source


def test_research_skill_saves_only_on_request_after_evidence_review() -> None:
    """調査Skillが下書きを独立に検証し、利用者が求めた場合だけRepositoryへ保存する。"""

    source = (SKILL_DIRECTORY / "research" / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter_source, _ = source.split("---", maxsplit=2)
    description = yaml.safe_load(frontmatter_source)["description"]
    assert "保存" in description
    assert "tmp/research/" in source
    assert "docs/research/" in source
    assert f"`{EVIDENCE_REVIEW_AGENT}`" in source
    assert "利用者が保存を求めた場合だけ" in source

    with (AGENT_DIRECTORY / f"{EVIDENCE_REVIEW_AGENT}.toml").open("rb") as file:
        instructions = tomllib.load(file)["developer_instructions"]
    for required in ("`verified`", "`incorrect`", "`unresolved`", "編集しない"):
        assert required in instructions


def test_claude_skills_receive_claude_only_frontmatter() -> None:
    """Claude Code専用の起動設定を、正本ではなく生成物へだけ加える。"""

    review = _frontmatter(CLAUDE_SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md")
    disallowed = {tool.strip() for tool in str(review["disallowed-tools"]).split(",")}
    assert {"Edit", "Write", "NotebookEdit"} <= disallowed
    assert review["effort"] == "high"

    research = _frontmatter(CLAUDE_SKILL_DIRECTORY / "research" / "SKILL.md")
    assert research["context"] == "fork"

    for skill_name in ("review-kvk-change", "research"):
        source = _frontmatter(SKILL_DIRECTORY / skill_name / "SKILL.md")
        assert set(source) == {"name", "description"}


def test_review_harness_separates_unresolved_concerns() -> None:
    """確認しきれない懸念を指摘と分け、承認判定へ含めない。"""

    skill_source = (SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "未確定の懸念" in skill_source
    assert "承認判定に含めない" in skill_source
    for name in sorted(CODE_REVIEW_AGENTS):
        with (AGENT_DIRECTORY / f"{name}.toml").open("rb") as source:
            instructions = tomllib.load(source)["developer_instructions"]
        assert "未確定" in instructions, name


def test_review_results_follow_template_and_are_posted_to_pull_request() -> None:
    """レビュー結果をテンプレートで残し、Pull Requestへ投稿する。"""

    template_path = (
        SKILL_DIRECTORY
        / "review-kvk-change"
        / "references"
        / "review-report-template.md"
    )
    template = template_path.read_text(encoding="utf-8")
    for heading in (
        "## AIレビュー結果",
        "### 承認判定",
        "### Must",
        "### Should",
        "### Nice",
        "### 未確定の懸念",
        "### 対応状況",
        "### 実施した検査",
    ):
        assert heading in template, heading
    assert "<!-- kvk-review" in template

    review_skill = (SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "references/review-report-template.md",
        "tmp/reviews/",
        "gh pr comment",
        "--body-file",
    ):
        assert required in review_skill, required

    pr_skill = (SKILL_DIRECTORY / "create-github-pr" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "tmp/reviews/" in pr_skill
    assert "gh pr comment" in pr_skill

    agents_policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "tmp/reviews/" in agents_policy
    assert "ADR 0022" in agents_policy


def _compact(text: str) -> str:
    """改行と空白を除き、文書の折り返し位置に依存せず規範文を照合できるようにする。"""

    return "".join(text.split())


def test_review_covers_document_only_changes_and_requirements() -> None:
    """文書だけの変更もレビューし、要件の正確さと漏れを独立した担当が確かめる。"""

    review_skill = _compact(
        (SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md").read_text(encoding="utf-8")
    )
    for required in (
        "「コードを変えていない」ことを理由に省略しない",
        "4つすべてを割り当てる",
        "`tmp/review-sources/`へ保存し、その絶対パスをすべてのレビュー担当へ渡す",
        "実運用の名前を含む資料をRepositoryへコミットしない",
        "割り当てるはずだった4つの観点（要件の観点を含む）",
        "実運用の参加者名は転記せず",
        "`tmp/review-sources/`への出典の保存",
        "出典と食い違う要件、要件どうしの矛盾",
        "「運用者への確認事項」",
    ):
        assert _compact(required) in review_skill, required

    with (AGENT_DIRECTORY / "kvk-requirements-reviewer.toml").open("rb") as source:
        definition = tomllib.load(source)
    assert definition["sandbox_mode"] == "read-only"
    instructions = _compact(definition["developer_instructions"])
    for required in (
        "必ず開いて要件と1件ずつ照合する",
        "tmp/review-sources/",
        "名前を転記しない",
        "考慮漏れ",
        "曖昧さ",
        "矛盾",
        "検証可能性",
        "要件ID",
        "運用者への確認事項",
        "契約として載る集結主名、人数、イベント時間は対象外とする",
        "基準ブランチにコミット済みのtests/とsample/の試験データにある名前は、レビュー結果へ書いてよい",
        "対象差分でtests/、sample/、文書へ新しく加わるデータが、出典の参加者一覧に由来しないかは必ず確かめる",
        "基準ブランチにコミット済みのREADMEとteam_master.jsonに契約として載る",
        "出典の参加者一覧に由来しないかは必ず確かめる",
        "Git管理外の本物のチームマスタ（--team-masterで指定するファイル、ADR 0026）にある"
        "集結主名、代理集結主名、役割、運用メモも秘密情報とする",
    ):
        assert _compact(required) in instructions, required

    template = (
        SKILL_DIRECTORY
        / "review-kvk-change"
        / "references"
        / "review-report-template.md"
    ).read_text(encoding="utf-8")
    assert "kvk-requirements-reviewer" in template
    assert "### 運用者への確認事項" in template

    agents_policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "ADR 0024" in agents_policy
    assert _compact("4つすべてを割り当て、レビューを省略しません") in _compact(
        agents_policy
    )

    # 3観点の時代の記述を残さない
    claude_policy = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for name, text in (
        ("AGENTS.md", agents_policy),
        ("review-report-template.md", template),
        ("CLAUDE.md", claude_policy),
    ):
        assert "3観点" not in text, name
        assert "3つのReview Agent" not in text, name

    # レビューを起動する手順も、文書だけの変更を対象にする
    pr_skill = (SKILL_DIRECTORY / "create-github-pr" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    implement_skill = (SKILL_DIRECTORY / "implement" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "重要な変更は`$review-kvk-change`" not in pr_skill
    assert "影響が大きい場合は`$review-kvk-change`" not in implement_skill
    for text in (pr_skill, implement_skill):
        assert "ADR 0024" in text
        assert _compact("文書だけの変更でも") in _compact(text)

    # 実運用の名前を含む出典とレビュー結果を管理対象の外に置く
    ignored = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/tmp/" in ignored


def test_review_is_repeated_after_findings_are_addressed() -> None:
    """指摘へ対応した後は、対応後の差分をもう一度レビューする。"""

    review_skill = _compact(
        (SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md").read_text(encoding="utf-8")
    )
    for required in (
        "対応後の差分に対して本Skillをもう一度実行する（再レビュー）",
        "前回の指摘ごとの判定（解消、一部解消、未解消、見送り）",
        "新しいコメントとして投稿",
    ):
        assert _compact(required) in review_skill, required

    for path in (
        PROJECT_ROOT / "AGENTS.md",
        SKILL_DIRECTORY / "implement" / "SKILL.md",
        SKILL_DIRECTORY / "create-github-pr" / "SKILL.md",
        PROJECT_ROOT
        / "docs"
        / "adr"
        / "0024-review-document-changes-and-requirements.md",
    ):
        text = _compact(path.read_text(encoding="utf-8"))
        assert _compact("再レビュー") in text, path.name


def test_review_scope_exceptions_and_rereview_termination_are_explicit() -> None:
    """4担当の一覧、見送れる変更の範囲、再レビューの対象と終わり方を固定する。"""

    review_skill_text = (SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    agents_policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for name in (
        "kvk-domain-reviewer",
        "kvk-architecture-reviewer",
        "kvk-test-reviewer",
        "kvk-requirements-reviewer",
    ):
        with (AGENT_DIRECTORY / f"{name}.toml").open("rb") as source:
            definition = tomllib.load(source)
        assert definition["sandbox_mode"] == "read-only", name
        assert f"`{name}`" in review_skill_text, name
        assert f"`{name}`" in agents_policy, name

    review_skill = _compact(review_skill_text)
    for required in (
        "要件ID、数値、否定、識別子、規則の対象を変える修正は誤字の修正に含めない",
        "利用者が承認した`Should`の見送りのPull Request本文への追記だけとする",
        "レビュー対象の差分で新しく加わる名前は、この対象外にしない",
        "Git管理外の本物のチームマスタ（`--team-master`で指定するファイル、ADR 0026）にある"
        "集結主名、代理集結主名、役割、運用メモも転記しない",
        "対象はPull Request全体の差分（基準ブランチからの差分）とし",
        "amendやrebaseで前回の`head`がなくなった場合は",
        "PRのhead（`gh pr view <番号> --json headRefOid`）が、レビューした版と同じであること",
        "`python tools/review_fingerprint.py --base <head> --target <PRのhead>`",
        "基準ブランチにコミット済みのREADME",
        "運用者への確認事項が未回答、または前回の`Must`の判定に「解消」以外がある: 承認不可",
        "変わっていれば改めて判定し、利用者がもう一度判断する",
        "前回の「見送り」の節の行と、「振り返り」の節の分類ごとの回数をすべて引き継ぐ",
        "委譲の前に主エージェントが有効な見送りの行ごとに、記録したパスごとのblobと",
        "パスがなくなっていれば「変わった」とみなす",
        "それ以降に投稿しなかった途中の結果の指摘を含めて書く",
        "| ハーネス（Skill、Review Agent、Hook、レビューの手順） | ADRを作るか更新する場合はその「判断」と、Pull Request本文の「判断と影響」 |",
        "| それ以外のコードと文書 | その規則を述べる正本",
        "要件定義書が基準ブランチにも今回の変更にもなければ",
        "| `web/`の補助ツールと、それを移植する`battle_timing` | `docs/requirements/web-tools/`の該当する要件定義書の「作成者の仮定」 |",
        "`docs/requirements/`の該当する要件定義書の「作成者の仮定」",
        "どの種類でも、目的関数や警告の表示を変える仮定は、Pull Request本文の「判断と影響」にも一覧で載せ",
        "記録先が要件定義書のときだけ、「作成者の仮定」の節がなければ作る",
        "要件定義書以外の記録先では節を作らず、該当する箇所に「（作成者の仮定）」と注記して書く",
        "注記を書けない正本（`team_master.json`などのJSON）では、Pull Request本文の「判断と影響」と、ADRを作る場合はその「判断」に書く",
        "共有記憶の「重要な判断」に「（作成者の仮定）」と注記して書く",
        "`$create-github-pr`は作成時に、そのbranchのセッション記録と記録先から本文の「判断と影響」へ写す",
        "記録したパスごとのblobがすべて同じなら",
        "場所のパスごとのblob（`path=blob`を並べる）",
        "影響の範囲にかかわらず確認事項にする",
        "統合するときに1件へまとめる",
        "対象を指定した場合も、`git status --short`に出る変更と",
        "結果の印の`diff`には、委譲の前に計算した指紋を書く",
        "pushの前に再レビューを重ねた場合は、最後の結果だけを投稿する",
        "状態を「無効（再判断した版）」として残し",
        "`$implement`がpushした直後に、この手順の確認を行ってから投稿する",
        "同じ`target`、`head`、`diff`の",
        "未コミットの変更がなくても常に",
        "未追跡のファイル（`git ls-files --others --exclude-standard`）",
        "委譲の前後で`git status --short`と`python tools/review_fingerprint.py --base <head>`の出力（指紋）を",
        "必須条件の判定、出力の可否、運用者の操作のどれかが変わる点だけとする",
        "各確認事項には推奨案を添え",
        "「保留」という回答も、回答済みとして扱う",
        "更新の直前に本文をもう一度取得し、最初に取得した本文と同じであることを確かめてから",
        '読み書きは`encoding="utf-8"`と`newline=""`で行い、改行を変えない',
        "`.codex/agents/`の同名の定義を読み",
        "`gh api user`のログイン名と同じ投稿者で",
        "投稿もpushもせず、保存したパスと理由を報告する",
        "「前回の指摘の判定」を「なし（初回のレビュー）」とし",
        "`Must`はリスクを受け入れても見送れず、必ず修正する",
        "今回の結果に`Must`がなく、前回の`Must`の判定がすべて「解消」である",
        "運用者への確認事項がすべて回答され、正本へ反映された",
        "判定の「見送り」は`Should`だけに使う",
        "修正した`Should`は再レビューする",
        "`gh`の認証やNetworkの失敗（手順8）で投稿できていない場合だけ、上書きを止めて",
        "PRがない、またはまだpushしていないために投稿しなかった場合は、上書きしてよい",
        "保存ファイルの「見送り」の節に、指摘の番号、題名、場所",
        "`gh pr view <番号> --json body`で現在の本文を取得する",
        "追記した部分を利用者へ示し、承認を得る",
        "`gh pr edit <番号> --body-file <そのファイル>`で更新する。違えば更新せず",
        "同じheadへレビュー結果を投稿し直さない",
        "要件定義書だけを直す回答は",
    ):
        assert _compact(required) in review_skill, required

    # Mustをリスク受容で見送れる旧い終わり方を、繰り返しを定めるすべての文書から除く
    implement_skill = _compact(
        (SKILL_DIRECTORY / "implement" / "SKILL.md").read_text(encoding="utf-8")
    )
    assert _compact("`Must`は見送れない") in implement_skill
    assert _compact("「見送り」の節に記録する") in implement_skill
    for name, text in (
        ("review-kvk-change", review_skill),
        ("implement", implement_skill),
        (
            "ADR 0024",
            _compact(
                (
                    PROJECT_ROOT
                    / "docs"
                    / "adr"
                    / "0024-review-document-changes-and-requirements.md"
                ).read_text(encoding="utf-8")
            ),
        ),
    ):
        assert _compact("リスクを受け入れるまで") not in text, name
        assert _compact("未解消の`Must`がなく") not in text, name

    # 見送れる変更は、レビューを起動するすべての手順で同じ3つに限る
    for path in (
        PROJECT_ROOT / "AGENTS.md",
        PROJECT_ROOT / "DEVELOPMENT.md",
        PROJECT_ROOT / ".github" / "pull_request_template.md",
        PROJECT_ROOT
        / "docs"
        / "adr"
        / "0024-review-document-changes-and-requirements.md",
        SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md",
        SKILL_DIRECTORY / "implement" / "SKILL.md",
        SKILL_DIRECTORY / "create-github-pr" / "SKILL.md",
    ):
        text = _compact(path.read_text(encoding="utf-8"))
        assert _compact("意味を変えない誤字の修正だけの変更") in text, path.name
        assert (
            _compact(
                "意味を変えない誤字の修正とそのセッションの共有記憶の記録だけを含む変更"
            )
            in text
        ), path.name
        assert "誤字の修正だけ" not in text.replace(
            "意味を変えない誤字の修正だけ", ""
        ), path.name

    adr = _compact(
        (
            PROJECT_ROOT
            / "docs"
            / "adr"
            / "0024-review-document-changes-and-requirements.md"
        ).read_text(encoding="utf-8")
    )
    for required in (
        "要件ID、数値、否定、識別子、規則の対象を変える修正",
        "対応状況を更新して投稿し直すとする点",
        "`Must`はリスクを受け入れても見送れない",
        "Pull Request本文の「判断と影響」へ書く",
        "本文への追記は`$review-kvk-change`が利用者の承認を得て行い、読み取り専用の例外に加える",
        "運用者への確認事項がすべて回答されて正本へ反映されるまで繰り返す",
        "基準ブランチにコミット済みの`tests/`と`sample/`の試験データにある名前は、レビュー結果へ書いてよい",
        "レビュー対象の差分で新しく加わるデータが出典に由来しないかは、引き続き検査する",
        "`tools/review_fingerprint.py`で記録し",
        "Readyにしてよいこと、委譲の前に計算すること、",
        "指紋は名前の変更を検出せずに計算し、未追跡のファイルを含める",
        "出典や回答どうしの衝突は、影響の範囲にかかわらず確認事項にする",
        "それ以外の細部は作成者が既定案を決め",
        "前回の`Must`に「解消」以外がある場合の承認判定は「承認不可」",
    ):
        assert _compact(required) in adr, required

    # PR作成時は、レビューしたheadを確かめてからReadyにし、見送りを本文へ写す
    pr_skill = _compact(
        (SKILL_DIRECTORY / "create-github-pr" / "SKILL.md").read_text(encoding="utf-8")
    )
    for required in (
        "同じ版を指さない場合は投稿せず、再レビューを求める",
        "`python tools/review_fingerprint.py --base <head> --target HEAD`",
        "同じ印の投稿がないこと",
        "満たさなければ再レビューを求め、Readyにしない",
        "「見送り」の節に記録があれば（「なし」でなければ）",
    ):
        assert _compact(required) in pr_skill, required
    pr_template = (PROJECT_ROOT / ".github" / "pull_request_template.md").read_text(
        encoding="utf-8"
    )
    assert "## 判断と影響" in pr_template

    template = (
        SKILL_DIRECTORY
        / "review-kvk-change"
        / "references"
        / "review-report-template.md"
    ).read_text(encoding="utf-8")
    assert "### 前回の指摘の判定" in template
    assert "### Must" in template
    assert template.index("### 前回の指摘の判定") < template.index("### Must")
    assert "解消／一部解消／未解消／見送り" in template
    assert "### 見送り" in template
    assert "diff=<tools/review_fingerprint.pyの出力>" in template
    assert _compact("前回までの行を状態ごとすべて引き継ぐ") in _compact(template)
    deferred_header = next(
        line
        for line in template.split("### 見送り", 1)[1].splitlines()
        if line.startswith("| #")
    )
    for column in ("題名", "場所", "場所のパスごとのblob", "レビューした版", "状態"):
        assert column in deferred_header, column
    assert "無効（再判断した版）" in template
    for path in (
        SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md",
        SKILL_DIRECTORY / "implement" / "SKILL.md",
        SKILL_DIRECTORY / "create-github-pr" / "SKILL.md",
        SKILL_DIRECTORY
        / "review-kvk-change"
        / "references"
        / "review-report-template.md",
    ):
        assert "diff=none" not in path.read_text(encoding="utf-8"), path.name
    assert _compact("`Must`は書かない") in _compact(template)


def test_review_improves_itself_after_each_response() -> None:
    """指摘へ対応するたびに自己点検し、繰り返す原因を自己点検リストへ足す。"""

    references = SKILL_DIRECTORY / "review-kvk-change" / "references"
    checklist = (references / "self-check.md").read_text(encoding="utf-8")
    rows = [line for line in checklist.splitlines() if re.match(r"^\| C\d+ \|", line)]
    assert rows, "自己点検リストに項目がない"
    # 番号はC1から欠けも重複もなく並ぶ（「次に空いている番号」の規則を確かめられるようにする）
    numbers = [int(re.match(r"^\| C(\d+) \|", line).group(1)) for line in rows]
    assert numbers == list(range(1, len(numbers) + 1)), numbers
    for line in rows:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 4 and all(cells), line
        source = r"(#\d+|[A-Za-z0-9][A-Za-z0-9._/-]*)"
        assert re.fullmatch(rf"{source}(、{source})*", cells[3]), line

    review_skill = _compact(
        (SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md").read_text(encoding="utf-8")
    )
    for required in (
        "作成者が`references/self-check.md`（自己点検リスト）を1項目ずつ確かめてから",
        "## 振り返る",
        "リストにない分類の指摘が、同じPull Requestの再レビューで2回以上現れたら",
        "レビューの中では`references/self-check.md`を編集しない",
        "最初に案を`references/self-check.md`へ反映し",
        "今回その分類が現れたら1を足す（件数は足さない）",
        "項目を足すか見直した後の再レビューで3回以上現れたら",
        "その案を出したPull Requestの番号を出所として書く",
        "Pull Requestがまだなければbranch名を書き",
        "基準ブランチにリストがなければ、このブランチのリストで次に空いている番号とする",
        "新しい番号の行に旧い番号を併記する",
        "繰り返しを終えた後に残った案は、投稿したレビュー結果に残し、別の場所へ写さない",
        "先に後者の回数を0に戻す。そのうえで、今回その分類が現れたら1を足す",
        "出所の列だけの変更は見直しに含めない",
        "委譲の前に伝える「今回の対応で『確かめること』を変えた分類」で決める",
        "差分だけでは決めない",
        "差分と照らして申告を確かめる",
        "コミットしないまま次の対応でC2を変えなければ",
        "申告がなければ委譲の前に作成者へ求める",
        "申告にあって差分にない分類は0に戻さず",
        "「見直した分類（作成者の申告）」として書く",
        "前回の結果の保存ファイルとその指摘と申告を担当へ渡し",
        "作成者は委譲の前に、今回の対応で自己点検リストの「確かめること」を変えた分類（なければ「なし」）を申告する",
        "申告にあって差分にない分類は0に戻さず、作成者へ確かめる",
        "照合に使う差分は、前回のレビューの`head`から作業ツリーまでとする",
        "そのコミットの申告は、それより後の最初の再レビューで1回だけ行う",
        "作成者が差分を示せない分類は申告から除く",
        "force pushを要しない基準ブランチのmergeで行い、コミットを伴うため利用者の明示を得る",
        "取り込んだ後の最初の対応で反映する",
        "Pull Requestがあれば、作成者は手順7の方法",
        "Pull Requestがまだなければ、Pull Request本文に載せる仮定を",
        "branch名のままでよい",
        "そのコミットとともに申告する",
        "次の対応の最初に基準ブランチを取り込み",
        "そのPull Requestの最新のレビュー結果から読んで反映する",
        "リストにない分類の後者の回数は「—」と書く",
        "次の対応で反映することは、項目ごとの承認を得ずに作成者が行う。利用者は2026-10-19にこれを承認した",
        "`AGENTS.md`の昇格の承認の例外",
    ):
        assert _compact(required) in review_skill, required
    for removed in (
        "前回の`head`がなくなった場合は、作成者が委譲の前に伝えた",
        "リストがないブランチやほかのPull Requestで出た案は",
        "昇格候補を経由するものも含め",
        "共有記憶の昇格候補（`docs/project-memory/candidates/`）へ書く",
        "`$change-kvk-rules`に従って正本の要件定義書",
    ):
        assert _compact(removed) not in review_skill, removed
    assert _compact("リストに足した項目") not in review_skill
    assert _compact("あらかじめ承認している") not in review_skill

    template = (references / "review-report-template.md").read_text(encoding="utf-8")
    assert template.index("### 振り返り") < template.index("### 実施した検査")
    assert (
        "| 原因の分類 | 今回の件数 | 現れた再レビューの回数 | 項目を足すか見直した後の回数 | 該当する指摘 |"
        in template
    )
    assert "足す項目の案（次の対応で反映）" in template

    implement_skill = _compact(
        (SKILL_DIRECTORY / "implement" / "SKILL.md").read_text(encoding="utf-8")
    )
    for required in (
        "ほかの指摘より先に、前回のレビュー結果の振り返りにある項目の案を",
        "pushしたら、まだ投稿していない`$review-kvk-change`の結果を、その手順3の確認を行ってから投稿する",
    ):
        assert _compact(required) in implement_skill, required
    assert _compact("共有記憶の昇格候補にある自己点検の案") not in implement_skill
    for required in (
        "自己点検リストがないブランチで繰り返しが続いているPull Requestがあれば、その最新のレビュー結果の案も反映する",
        "同じ案を二重に足さない",
        "案の文が該当する行の「確かめること」にすでにあるかで反映済みの案を確かめ",
        "利用者の明示を得て基準ブランチをmergeで取り込んでから反映する",
        "「確かめること」を変えた分類を申告してから",
    ):
        assert _compact(required) in implement_skill, required
    assert "見直した分類（作成者の申告）" in template
    pr_skill = _compact(
        (SKILL_DIRECTORY / "create-github-pr" / "SKILL.md").read_text(encoding="utf-8")
    )
    assert _compact("作成者の仮定のうち、Pull Request本文に載せるもの") in pr_skill
    for required in (
        "セッション記録の「重要な判断」にある「（作成者の仮定）」",
        "「結果を報告する」の表とその後の段落",
        "後で覆して記録先から消えた仮定は写さない",
    ):
        assert _compact(required) in pr_skill, required
    assert "<C…、またはなし>" in template

    adr = _compact(
        (
            PROJECT_ROOT
            / "docs"
            / "adr"
            / "0024-review-document-changes-and-requirements.md"
        ).read_text(encoding="utf-8")
    )
    for required in (
        "レビューは読み取り専用のままとする",
        "次の対応で反映することは、項目ごとの承認を要らないこととする（利用者が2026-10-19に承認）",
        "回数は、分類が現れた再レビューの回数で数える",
        "Review Agentの定義は基準を写さず、Skillを参照する。",
        "記録先は変更の種類ごとに`$review-kvk-change`の表に従い",
        "ハーネスの変更でADRを作るか更新する場合に限る",
        "作成者の仮定を本文へ載せるときも、同じ方法で利用者の承認を得る",
    ):
        assert _compact(required) in adr, required
    for removed in (
        "ADRの「作成者の仮定」",
        "作成者が解釈した例外",
        "経由するものも含めて項目ごとの承認を要らない",
    ):
        assert _compact(removed) not in adr, removed
    agents_policy = _compact((PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    assert (
        _compact(
            "自己点検リストへの反映は、`$review-kvk-change`の「振り返る」の手順（ADR 0024）に従い"
        )
        in agents_policy
    )

    for path in (
        PROJECT_ROOT / "AGENTS.md",
        SKILL_DIRECTORY / "implement" / "SKILL.md",
        PROJECT_ROOT
        / "docs"
        / "adr"
        / "0024-review-document-changes-and-requirements.md",
    ):
        assert "self-check.md" in path.read_text(encoding="utf-8"), path.name


def test_review_agents_refer_to_the_skill_for_question_rules() -> None:
    """Review Agentは確認事項の基準を写さず、Skillを参照する（写しのずれを防ぐ）。"""

    review_skill = _compact(
        (SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md").read_text(encoding="utf-8")
    )
    # 参照先の見出しの名前が変わると、TOMLからの参照が切れる
    source = (SKILL_DIRECTORY / "review-kvk-change" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    section = source.split("\n## 結果を報告する\n", 1)[1].split("\n## ", 1)[0]
    # 記録先の表の行が消えたら気づけるよう、行の数を確かめる
    table = section.split("| 変更の種類 | 作成者の仮定の記録先 |", 1)[1].split(
        "\n\n", 1
    )[0]
    rows = [
        line
        for line in table.splitlines()
        if line.startswith("| ") and "---" not in line
    ]
    assert len(rows) == 4, rows
    for rule in (
        "影響の範囲にかかわらず確認事項にする",
        "必須条件の判定、出力の可否、運用者の操作のどれかが変わる点だけとする",
        "| 変更の種類 | 作成者の仮定の記録先 |",
    ):
        assert _compact(rule) in _compact(section), rule
    assert _compact("影響の範囲にかかわらず確認事項にする") in review_skill
    for name in (
        "kvk-domain-reviewer",
        "kvk-architecture-reviewer",
        "kvk-test-reviewer",
        "kvk-requirements-reviewer",
    ):
        with (AGENT_DIRECTORY / f"{name}.toml").open("rb") as source:
            instructions = _compact(tomllib.load(source)["developer_instructions"])
        assert (
            _compact(
                "`.agents/skills/review-kvk-change/SKILL.md`の「結果を報告する」に従う"
            )
            in instructions
        ), name
        assert _compact("運用者の操作が変わる点だけに絞り") not in instructions, name


def test_implement_skill_isolates_parallel_sessions_with_worktrees() -> None:
    """実装Skillが別Sessionの使用中にworktreeへ移り、完了を検証可能な形で示す。"""

    source = (SKILL_DIRECTORY / "implement" / "SKILL.md").read_text(encoding="utf-8")
    for required in (
        "use_separate_worktree",
        "discard",
        ".worktrees/",
        "git worktree add",
        "会話に表示",
    ):
        assert required in source

    claude_source = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "/goal" in claude_source
    assert "EnterWorktree" in claude_source

    agents_policy = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "worktree" in agents_policy


def _load_sync_module() -> ModuleType:
    """同期Scriptをモジュールとして読み込む。"""

    spec = importlib.util.spec_from_file_location("sync_agent_config", SYNC_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _frontmatter(path: Path) -> dict[str, object]:
    """MarkdownのFrontmatterを辞書として返す。"""

    _, source, _ = path.read_text(encoding="utf-8").split("---", maxsplit=2)
    loaded = yaml.safe_load(source)
    assert isinstance(loaded, dict)
    return loaded


def test_claude_md_imports_shared_agents_policy() -> None:
    """Claude Codeが共通規約としてAGENTS.mdを読み込む。"""

    source = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "\n@AGENTS.md\n" in source
    assert "tools/sync_agent_config.py" in source
    assert JAPANESE_TEXT_PATTERN.search(source)
    assert ".claude/settings.local.json" in (PROJECT_ROOT / ".gitignore").read_text(
        encoding="utf-8"
    )


def test_claude_config_is_synchronized_with_codex_sources() -> None:
    """Claude Code向けSkillとAgentが正本から生成された状態と一致する。"""

    module = _load_sync_module()
    assert module.find_differences(PROJECT_ROOT) == []


def test_claude_skills_mirror_shared_skills_except_codex_only() -> None:
    """Codex専用以外のSkillをClaude Codeへ同じ名前で提供する。"""

    source_skills = {path.parent.name for path in SKILL_DIRECTORY.glob("*/SKILL.md")}
    claude_skills = {
        path.parent.name for path in CLAUDE_SKILL_DIRECTORY.glob("*/SKILL.md")
    }
    assert claude_skills == source_skills - CODEX_ONLY_SKILLS
    assert not list(CLAUDE_SKILL_DIRECTORY.glob("*/agents/openai.yaml"))

    for skill_name in claude_skills:
        frontmatter = _frontmatter(CLAUDE_SKILL_DIRECTORY / skill_name / "SKILL.md")
        assert frontmatter["name"] == skill_name
        metadata = yaml.safe_load(
            (SKILL_DIRECTORY / skill_name / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
        )
        explicit_only = (metadata.get("policy") or {}).get(
            "allow_implicit_invocation"
        ) is False
        assert (frontmatter.get("disable-model-invocation") is True) == explicit_only


def test_claude_review_agents_have_no_edit_tools() -> None:
    """Claude Code向けReview Agentが編集Toolを持たず正本の指示を引き継ぐ。"""

    paths = sorted(CLAUDE_AGENT_DIRECTORY.glob("*.md"))
    assert {path.stem for path in paths} == EXPECTED_AGENTS

    for path in paths:
        frontmatter = _frontmatter(path)
        with (AGENT_DIRECTORY / f"{path.stem}.toml").open("rb") as source:
            definition = tomllib.load(source)
        assert frontmatter["name"] == definition["name"]
        assert frontmatter["description"] == definition["description"]
        assert frontmatter["permissionMode"] == "plan"
        assert frontmatter["effort"] == "high"
        # 主会話のモデルを継承させず、担当の重さで固定する（ADR 0030）。
        expected_model = "opus" if path.stem in HEAVY_REVIEW_AGENTS else "sonnet"
        assert frontmatter["model"] == expected_model, path.stem
        # 過去の最大33ターンに余裕を持たせ、証拠の照合は主張の数に比例して長くなる。
        # アーキテクチャ担当は仕様とソースの突き合わせで40ターンに達したため広げた。
        long_agents = {EVIDENCE_REVIEW_AGENT, "kvk-architecture-reviewer"}
        expected_turns = 60 if path.stem in long_agents else 40
        assert frontmatter["maxTurns"] == expected_turns, path.stem
        tools = {tool.strip() for tool in str(frontmatter["tools"]).split(",")}
        assert tools.isdisjoint({"Edit", "Write", "NotebookEdit"})
        if path.stem == EVIDENCE_REVIEW_AGENT:
            # 出典を開いて照合するため、Web取得を持ちShellを持たない。
            assert {"WebSearch", "WebFetch"} <= tools
            assert "Bash" not in tools
        body = path.read_text(encoding="utf-8")
        assert definition["developer_instructions"].strip() in body


def test_sync_detects_and_repairs_drift(tmp_path: Path) -> None:
    """同期Scriptが不一致と不要な生成物を検出し、修復する。"""

    module = _load_sync_module()
    skill = tmp_path / ".agents" / "skills" / "sample"
    (skill / "agents").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: sample\ndescription: 例\n---\n\n本文\n", encoding="utf-8"
    )
    (skill / "agents" / "openai.yaml").write_text(
        "policy:\n  allow_implicit_invocation: false\n", encoding="utf-8"
    )
    codex_only = tmp_path / ".agents" / "skills" / "codex-handoff"
    codex_only.mkdir(parents=True)
    (codex_only / "SKILL.md").write_text(
        "---\nname: codex-handoff\ndescription: 例\n---\n本文\n", encoding="utf-8"
    )
    agents = tmp_path / ".codex" / "agents"
    agents.mkdir(parents=True)
    (agents / "reviewer.toml").write_text(
        'name = "reviewer"\ndescription = "説明"\n'
        'model_reasoning_effort = "high"\ndeveloper_instructions = "指示"\n',
        encoding="utf-8",
    )

    assert module.main(["--check"], root=tmp_path) == 1
    assert module.main([], root=tmp_path) == 0
    assert module.find_differences(tmp_path) == []

    generated_skill = tmp_path / ".claude" / "skills" / "sample" / "SKILL.md"
    assert "disable-model-invocation: true" in generated_skill.read_text(
        encoding="utf-8"
    )
    assert not (tmp_path / ".claude" / "skills" / "codex-handoff").exists()
    assert (tmp_path / ".claude" / "agents" / "reviewer.md").is_file()

    generated_skill.write_text("手動編集\n", encoding="utf-8")
    stale = tmp_path / ".claude" / "skills" / "removed" / "SKILL.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("古い\n", encoding="utf-8")
    assert module.find_differences(tmp_path) == [
        "不一致: .claude/skills/sample/SKILL.md",
        "不要: .claude/skills/removed/SKILL.md",
    ]

    module.main([], root=tmp_path)
    assert module.find_differences(tmp_path) == []
    assert not stale.parent.exists()


def test_hidden_words_rule_covers_every_outward_text() -> None:
    """伏せる語の規則を正本の1か所に置き、外へ出る文を作る手順が参照する（ADR 0026）。"""

    agents_policy = _compact((PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    assert (
        _compact(
            "ADR 0026で伏せたゲーム名とイベント名は、追跡するファイルに加え、"
            "コミットメッセージ、branch名、Pull Requestのタイトルと本文、Issue、"
            "レビュー結果とコメントにも書きません"
        )
        in agents_policy
    )
    assert (
        _compact(
            "本物の参加者一覧と、それから作った出力も、同じく書きません。確認資料に載せる出力は、"
            "`sample/`か架空の参加者一覧を、`--team-master`を付けずに同梱の例で編成して作ります"
        )
        in agents_policy
    )
    assert (
        _compact(
            "Git管理外の本物のチームマスタにある集結主、代理集結主、役割、運用メモも、"
            "同じく書きません"
        )
        in agents_policy
    )
    pull_request = (SKILL_DIRECTORY / "create-github-pr" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    template = (PROJECT_ROOT / ".github" / "pull_request_template.md").read_text(
        encoding="utf-8"
    )
    assert _compact("`--team-master`を付けずに同梱の例で編成した") in _compact(template)
    assert _compact(
        "確認資料は`AGENTS.md`の伏せる語の規則（ADR 0026）に従って作る"
    ) in _compact(pull_request)
    # pushした後では消せないため、branch名とコミットメッセージ、コミットの内容の確認は
    # pushより前に置く。品質ゲート全体は、明示されたDraftと両立するようReadyの条件に留める。
    compact_pull_request = _compact(pull_request)
    verify = compact_pull_request.index(_compact("## Pull Requestの対象を検証する"))
    branch_check = compact_pull_request.index(
        _compact(
            "branch名と`origin/<base>..HEAD`のコミットメッセージが`AGENTS.md`の伏せる語の規則"
        )
    )
    scope_check = compact_pull_request.index(
        _compact(
            'python -m pytest tests/test_repository_scope.py tests/test_team_master_repository.py -k "hidden_words or placeholder"'
        )
    )
    push = compact_pull_request.index(_compact("git push --set-upstream"))
    assert verify < branch_check < scope_check < push
    assert (
        'python -m pytest tests/test_repository_scope.py tests/test_team_master_repository.py -k "hidden_words or placeholder"'
        in pull_request
    )
    # テストの名前を変えると、`-k`の絞り込みから黙って外れるため、選ばれるテストを固定する。
    selected = set()
    for test_file in ("test_repository_scope.py", "test_team_master_repository.py"):
        tree = ast.parse(
            (PROJECT_ROOT / "tests" / test_file).read_text(encoding="utf-8")
        )
        selected |= {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("test_")
            and ("hidden_words" in node.name or "placeholder" in node.name)
        }
    assert selected == {
        "test_hidden_words_are_detected_after_normalization",
        "test_tracked_files_do_not_contain_hidden_words",
        "test_bundled_master_uses_placeholder_roles_and_notes",
    }
    before_push = compact_pull_request[branch_check:push]
    for required in (
        "当たる場合や伏せる語の検査が失敗した場合は、Draftでもpushせず",
        "品質ゲート全体（`python tools/check.py`）の成功は、従来どおりReadyの条件とする",
        "この検査はHEADの内容だけを見る",
    ):
        assert _compact(required) in before_push, required
    assert (
        _compact("すでにpushしたbranchやコミットが当たる場合は、Pull Requestを作らず")
        in compact_pull_request
    )
    implement = (SKILL_DIRECTORY / "implement" / "SKILL.md").read_text(encoding="utf-8")
    finish = _compact(implement[implement.index("## 仕上げる") :])
    assert (
        _compact(
            "コミットとpushの前に、コミットメッセージとbranch名が`AGENTS.md`の伏せる語の規則"
        )
        in finish
    )
    hidden_items = (
        "実運用の参加者情報",
        "本物のチームマスタ（集結主、代理集結主、役割、運用メモ）",
        "本物の参加者一覧から作った出力",
        "ADR 0026で伏せたゲーム名とイベント名",
    )
    github = PROJECT_ROOT / ".github"
    # 画面から書く人が読む注意と、必須の確認欄の両方に、伏せる対象をすべて挙げる。
    for issue_template in ("bug_report.yml", "feature_request.yml"):
        form = yaml.safe_load(
            (github / "ISSUE_TEMPLATE" / issue_template).read_text(encoding="utf-8")
        )
        notice = _compact(form["body"][0]["attributes"]["value"])
        checks = {field["id"]: field for field in form["body"] if "id" in field}
        labels = _compact(
            "".join(
                option["label"]
                for option in checks["sensitive-data-check"]["attributes"]["options"]
            )
        )
        for required in hidden_items:
            assert _compact(required) in notice, (issue_template, "注意", required)
            assert _compact(required) in labels, (issue_template, "確認欄", required)
    template_notice, template_checks = template.split("\n## 確認\n", 1)
    for required in hidden_items:
        assert _compact(required) in _compact(template_notice), required
    assert _compact(
        "- [ ] タイトル、本文、branch名、コミットメッセージが`AGENTS.md`の伏せる語の規則に"
        "当たらない"
    ) in _compact(template_checks)
    rules_skill = (SKILL_DIRECTORY / "change-kvk-rules" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert _compact("`AGENTS.md`の伏せる語の規則（ADR 0026）") in _compact(rules_skill)
    reference = _compact("`AGENTS.md`の伏せる語の規則（ADR 0026）")
    for skill in (
        "create-github-pr",
        "implement",
        "manage-github-issue",
        "review-kvk-change",
    ):
        text = (SKILL_DIRECTORY / skill / "SKILL.md").read_text(encoding="utf-8")
        assert reference in _compact(text), skill
    with (AGENT_DIRECTORY / "kvk-requirements-reviewer.toml").open("rb") as source:
        instructions = tomllib.load(source)["developer_instructions"]
    assert _compact("AGENTS.mdの伏せる語の規則（ADR 0026）") in _compact(instructions)
