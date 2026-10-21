"""Codex向けの正本からClaude Code向けのSkillとReview Agentを生成する。

正本は`.agents/skills/`と`.codex/agents/`であり、`.claude/skills/`と
`.claude/agents/`は本Scriptが生成する複製である。`--check`は生成結果と
Repository上の内容が一致するかだけを確認し、ファイルを変更しない。
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL_DIRECTORY = Path(".agents") / "skills"
SOURCE_AGENT_DIRECTORY = Path(".codex") / "agents"
CLAUDE_SKILL_DIRECTORY = Path(".claude") / "skills"
CLAUDE_AGENT_DIRECTORY = Path(".claude") / "agents"

# Codexの機能だけを操作するSkillはClaude Codeへ複製しない。
CODEX_ONLY_SKILLS = frozenset({"codex-handoff", "git-guardrails-codex"})
# Codex UI専用のメタデータはClaude Codeでは使用しない。
CODEX_METADATA_DIRECTORY = "agents"
# Review Agentは編集Toolを持たず、読み取りと差分確認だけを行う。
CLAUDE_REVIEWER_TOOLS = "Read, Grep, Glob, Bash"
# 既定と異なるToolが必要なAgent。証拠Reviewerは出典を開くがShellを使わない。
CLAUDE_AGENT_TOOLS = {"evidence-reviewer": "Read, Grep, Glob, WebSearch, WebFetch"}
# Codexが解釈しないClaude Code専用の起動設定。正本のFrontmatterは共通項目だけに保つ。
# disallowed-toolsは次の利用者Messageで解除されるため、後続の修正依頼を妨げない。
CLAUDE_SKILL_SETTINGS: dict[str, dict[str, str]] = {
    "research": {"context": "fork"},
    "review-kvk-change": {
        "disallowed-tools": "Edit, Write, NotebookEdit",
        "effort": "high",
    },
}
GENERATED_NOTICE = (
    "<!-- このファイルは tools/sync_agent_config.py が{source}から生成します。"
    "直接編集せず、正本を変更してから同期してください。 -->"
)


@dataclass(frozen=True, slots=True)
class GeneratedFile:
    """生成先の相対パスと内容を保持する。"""

    path: Path
    content: bytes


def _normalize(content: bytes) -> bytes:
    """改行差だけで不一致と判定しないようにLFへ揃える。"""

    return content.replace(b"\r\n", b"\n")


def _is_explicit_only(skill_directory: Path) -> bool:
    """Codexで暗黙起動を禁止したSkillかを返す。"""

    metadata_path = skill_directory / CODEX_METADATA_DIRECTORY / "openai.yaml"
    if not metadata_path.is_file():
        return False
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
    policy = metadata.get("policy") or {}
    return policy.get("allow_implicit_invocation") is False


def _claude_skill_source(
    source: str,
    source_path: Path,
    explicit_only: bool,
    settings: dict[str, str] | None = None,
) -> str:
    """SKILL.mdへClaude Code用の起動設定と生成元の注記を加える。"""

    if not source.startswith("---\n"):
        raise ValueError(f"{source_path}: Frontmatterがありません")
    _, frontmatter, body = source.split("---\n", maxsplit=2)
    if explicit_only:
        frontmatter += "disable-model-invocation: true\n"
    if settings:
        frontmatter += yaml.safe_dump(
            settings, allow_unicode=True, sort_keys=False, width=1000
        )
    notice = GENERATED_NOTICE.format(source=source_path.as_posix())
    return f"---\n{frontmatter}---\n\n{notice}\n{body}"


def _skill_files(root: Path) -> list[GeneratedFile]:
    """Codex向けSkillからClaude Code向けSkillを生成する。"""

    generated: list[GeneratedFile] = []
    for skill_directory in sorted((root / SOURCE_SKILL_DIRECTORY).iterdir()):
        if not (skill_directory / "SKILL.md").is_file():
            continue
        if skill_directory.name in CODEX_ONLY_SKILLS:
            continue

        target_directory = CLAUDE_SKILL_DIRECTORY / skill_directory.name
        explicit_only = _is_explicit_only(skill_directory)
        for path in sorted(skill_directory.rglob("*")):
            relative = path.relative_to(skill_directory)
            if not path.is_file() or relative.parts[0] == CODEX_METADATA_DIRECTORY:
                continue
            if "__pycache__" in relative.parts:
                continue

            content = path.read_bytes()
            if relative == Path("SKILL.md"):
                source = _claude_skill_source(
                    _normalize(content).decode("utf-8"),
                    path.relative_to(root),
                    explicit_only,
                    CLAUDE_SKILL_SETTINGS.get(skill_directory.name),
                )
                content = source.encode("utf-8")
            generated.append(GeneratedFile(target_directory / relative, content))
    return generated


def _agent_files(root: Path) -> list[GeneratedFile]:
    """CodexのReview Agent定義からClaude CodeのSubagent定義を生成する。"""

    generated: list[GeneratedFile] = []
    for path in sorted((root / SOURCE_AGENT_DIRECTORY).glob("*.toml")):
        with path.open("rb") as source:
            definition = tomllib.load(source)
        frontmatter = yaml.safe_dump(
            {
                "name": definition["name"],
                "description": definition["description"],
                "tools": CLAUDE_AGENT_TOOLS.get(path.stem, CLAUDE_REVIEWER_TOOLS),
                "permissionMode": "plan",
                "effort": definition.get("model_reasoning_effort", "high"),
            },
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        )
        notice = GENERATED_NOTICE.format(source=path.relative_to(root).as_posix())
        instructions = definition["developer_instructions"].strip()
        content = f"---\n{frontmatter}---\n\n{notice}\n\n{instructions}\n"
        generated.append(
            GeneratedFile(CLAUDE_AGENT_DIRECTORY / f"{path.stem}.md", content.encode())
        )
    return generated


def generate(root: Path) -> list[GeneratedFile]:
    """生成すべきClaude Code向けファイルの一覧を返す。"""

    return [*_skill_files(root), *_agent_files(root)]


def _existing_files(root: Path) -> set[Path]:
    """生成先Directoryに現在存在するファイルを返す。"""

    existing: set[Path] = set()
    for directory in (CLAUDE_SKILL_DIRECTORY, CLAUDE_AGENT_DIRECTORY):
        absolute = root / directory
        if not absolute.is_dir():
            continue
        for path in absolute.rglob("*"):
            relative = path.relative_to(root)
            if path.is_file() and "__pycache__" not in relative.parts:
                existing.add(relative)
    return existing


def find_differences(root: Path) -> list[str]:
    """生成結果とRepositoryの差分を利用者向けの文で返す。"""

    expected = {file.path: file.content for file in generate(root)}
    existing = _existing_files(root)
    differences: list[str] = []
    for path, content in sorted(expected.items()):
        target = root / path
        if not target.is_file():
            differences.append(f"不足: {path.as_posix()}")
        elif _normalize(target.read_bytes()) != _normalize(content):
            differences.append(f"不一致: {path.as_posix()}")
    for path in sorted(existing - set(expected)):
        differences.append(f"不要: {path.as_posix()}")
    return differences


def synchronize(root: Path) -> list[str]:
    """生成結果を書き込み、不要な生成物を削除して変更内容を返す。"""

    changes = find_differences(root)
    expected = generate(root)
    expected_paths = {file.path for file in expected}
    for path in _existing_files(root) - expected_paths:
        (root / path).unlink()
    for file in expected:
        target = root / file.path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or _normalize(target.read_bytes()) != _normalize(
            file.content
        ):
            target.write_bytes(file.content)
    for directory in (CLAUDE_SKILL_DIRECTORY, CLAUDE_AGENT_DIRECTORY):
        absolute = root / directory
        if not absolute.is_dir():
            continue
        for path in sorted(absolute.rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    return changes


def create_argument_parser() -> argparse.ArgumentParser:
    """同期Scriptの引数Parserを生成する。"""

    parser = argparse.ArgumentParser(
        description="Codex向けのSkillとReview AgentをClaude Code向けへ同期します。"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="ファイルを変更せず、同期が必要な場合に非0で終了する",
    )
    return parser


def main(argv: list[str] | None = None, root: Path = PROJECT_ROOT) -> int:
    """同期または同期確認を実行する。"""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            # Windows CIなど非UTF-8のConsoleでも日本語の出力で失敗しないようにする。
            reconfigure(encoding="utf-8", errors="replace")
    args = create_argument_parser().parse_args(argv)
    if args.check:
        differences = find_differences(root)
        if differences:
            for difference in differences:
                print(difference, file=sys.stderr)
            print(
                "Claude Code向け設定が正本と一致しません。"
                "python tools/sync_agent_config.py を実行してください。",
                file=sys.stderr,
            )
            return 1
        print("Claude Code向け設定は正本と一致しています。")
        return 0

    changes = synchronize(root)
    for change in changes:
        print(change)
    print(f"Claude Code向け設定を同期しました（変更 {len(changes)} 件）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
