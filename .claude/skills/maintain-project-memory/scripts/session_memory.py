"""変更セッションの判定、共有記憶の生成、索引と形式の検証を行う。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[4]
MEMORY_ROOT = PROJECT_ROOT / "docs" / "project-memory"
SESSION_ROOT = MEMORY_ROOT / "sessions"
CANDIDATE_ROOT = MEMORY_ROOT / "candidates"
INDEX_PATH = MEMORY_ROOT / "INDEX.md"
MEMORY_PATH_PREFIX = "docs/project-memory/"
SESSION_STATUSES = {"current", "superseded"}
# 同じタグの記憶がこの件数に達したら、昇格候補の検討を促す。
PROMOTION_HINT_THRESHOLD = 3
# 指定を省略したSessionへ付く既定タグは、反復の根拠として扱わない。
DEFAULT_SESSION_TAG = "repository-change"
# 最後の操作からこの時間内の別Sessionを、同じ作業ツリーを使用中とみなす。
# finishしないまま終わったSessionの開始状態が残っても、時間経過で対象から外れる。
ACTIVE_SESSION_WINDOW = timedelta(hours=3)
CANDIDATE_STATUSES = {
    "observed",
    "candidate",
    "ready",
    "promoted",
    "rejected",
    "superseded",
}
PROMOTION_TARGETS = {
    "agents-guidance",
    "skill",
    "script",
    "reference",
    "product-contract",
    "adr",
    "domain-model",
    "review-agent",
    "plugin",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{16,}\b"),
    re.compile(
        r"(?i)\b(?:api[_ -]?key|password|secret|token)\s*[:=]\s*"
        r"[\"']?[A-Za-z0-9_./+=-]{12,}"
    ),
)


class ProjectMemoryError(RuntimeError):
    """利用者へ表示できる共有記憶管理エラー。"""


def _now() -> datetime:
    """UTCの現在時刻を返す。"""

    return datetime.now(UTC).replace(microsecond=0)


def _format_datetime(value: datetime) -> str:
    """時刻をUTCのISO 8601形式へ変換する。"""

    return value.isoformat().replace("+00:00", "Z")


def _run_git(*arguments: str) -> bytes:
    """Repository直下でGitを実行し、標準出力を返す。"""

    completed = subprocess.run(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ProjectMemoryError(f"Gitコマンドに失敗しました: {message}")
    return completed.stdout


def _git_text(*arguments: str) -> str:
    """Gitの標準出力をUTF-8文字列として返す。"""

    return _run_git(*arguments).decode("utf-8", errors="surrogateescape").strip()


def _decode_null_paths(payload: bytes) -> set[str]:
    """NUL区切りのGitパスを文字列集合へ変換する。"""

    return {
        item.decode("utf-8", errors="surrogateescape")
        for item in payload.split(b"\0")
        if item
    }


def _is_memory_path(path: str) -> bool:
    """共有記憶自身のパスか判定する。"""

    normalized = path.replace("\\", "/")
    return normalized == MEMORY_PATH_PREFIX.rstrip("/") or normalized.startswith(
        MEMORY_PATH_PREFIX
    )


def _fingerprint(path: str) -> str:
    """Repository内パスの現在内容を比較可能な文字列へ変換する。"""

    target = PROJECT_ROOT / path
    if target.is_symlink():
        value = f"symlink:{target.readlink()}".encode()
    elif target.is_file():
        value = target.read_bytes()
    elif target.exists():
        value = b"<directory>"
    else:
        value = b"<missing>"
    return hashlib.sha256(value).hexdigest()


def _worktree_snapshot() -> dict[str, str]:
    """Git管理対象の差分と未追跡ファイルの内容Hashを取得する。"""

    paths = _decode_null_paths(_run_git("diff", "HEAD", "--name-only", "-z", "--"))
    paths.update(
        _decode_null_paths(
            _run_git("ls-files", "--others", "--exclude-standard", "-z", "--")
        )
    )
    return {
        path: _fingerprint(path) for path in sorted(paths) if not _is_memory_path(path)
    }


def _state_directory() -> Path:
    """Repositoryごとに分離した一時状態Directoryを返す。"""

    repository_key = hashlib.sha256(str(PROJECT_ROOT).encode()).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / "kvk-team-builder-memory" / repository_key


def _state_path(session_id: str) -> Path:
    """Session識別子に対応する状態ファイルを返す。"""

    if not re.fullmatch(r"[A-Za-z0-9-]+", session_id):
        raise ProjectMemoryError("session_idは英数字とHyphenだけで指定してください。")
    return _state_directory() / f"{session_id}.json"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    """JSONを同一Directory内で原子的に置き換える。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary_path.replace(path)


def _read_state(session_id: str) -> dict[str, Any]:
    """開始時状態を読み、必要な型を確認する。"""

    path = _state_path(session_id)
    if not path.is_file():
        raise ProjectMemoryError(
            f"開始時状態がありません。先にstartを実行してください: {session_id}"
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("repository") != str(PROJECT_ROOT):
        raise ProjectMemoryError(
            "開始時状態のRepositoryが現在のRepositoryと一致しません。"
        )
    return value


def _parse_datetime(value: object) -> datetime | None:
    """状態ファイルのUTC時刻を読み、不正な値はNoneとして扱う。"""

    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _other_active_sessions(session_id: str, now: datetime) -> list[dict[str, str]]:
    """同じ作業ツリーで最近操作された別Sessionを返す。"""

    sessions = []
    for path in sorted(_state_directory().glob("*.json")):
        if path.stem == session_id:
            continue
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(state, dict) or state.get("repository") != str(PROJECT_ROOT):
            continue
        last_seen_at = state.get("last_seen_at", state.get("started_at"))
        last_seen = _parse_datetime(last_seen_at)
        if last_seen is None or now - last_seen > ACTIVE_SESSION_WINDOW:
            continue
        sessions.append(
            {
                "session_id": path.stem,
                "started_at": str(state.get("started_at")),
                "last_seen_at": str(last_seen_at),
            }
        )
    return sessions


def _changed_paths(
    before: dict[str, str], after: dict[str, str], excluded: set[str]
) -> set[str]:
    """開始時から内容または状態が変わったパスを返す。"""

    return {
        path
        for path in before.keys() | after.keys()
        if before.get(path) != after.get(path) and path not in excluded
    }


def _committed_paths(base_commit: str, final_commit: str) -> set[str]:
    """開始後にCommitされた共有記憶以外のパスを返す。"""

    if base_commit == final_commit:
        return set()
    paths = _decode_null_paths(
        _run_git("diff", "--name-only", "-z", base_commit, final_commit, "--")
    )
    return {path for path in paths if not _is_memory_path(path)}


def _preexisting_committed_paths(
    committed_paths: set[str],
    before: dict[str, str],
    after: dict[str, str],
) -> set[str]:
    """開始前の差分をそのままCommitしただけのパスを返す。"""

    return {
        path
        for path in committed_paths
        if path in before and path not in after and _fingerprint(path) == before[path]
    }


def _frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """MarkdownのYAML Frontmatterと本文を読む。"""

    source = path.read_text(encoding="utf-8")
    if not source.startswith("---\n"):
        raise ProjectMemoryError(
            f"Frontmatterがありません: {path.relative_to(PROJECT_ROOT)}"
        )
    try:
        frontmatter_source, body = source[4:].split("\n---\n", maxsplit=1)
    except ValueError as error:
        raise ProjectMemoryError(
            f"Frontmatterの終端がありません: {path.relative_to(PROJECT_ROOT)}"
        ) from error
    value = yaml.safe_load(frontmatter_source)
    if not isinstance(value, dict):
        raise ProjectMemoryError(
            f"FrontmatterはMappingで指定してください: {path.relative_to(PROJECT_ROOT)}"
        )
    return value, body


def _record_paths(root: Path) -> list[Path]:
    """指定Directory配下のMarkdown記録を返す。"""

    if not root.exists():
        return []
    return sorted(root.rglob("*.md"))


def _relative_link(path: Path) -> str:
    """INDEX.mdから見た相対リンクをPOSIX形式で返す。"""

    return path.relative_to(MEMORY_ROOT).as_posix()


def _index_source() -> str:
    """現在の記録から決定的な索引本文を生成する。"""

    sessions = [(_frontmatter(path)[0], path) for path in _record_paths(SESSION_ROOT)]
    candidates = [
        (_frontmatter(path)[0], path) for path in _record_paths(CANDIDATE_ROOT)
    ]
    lines = [
        "# プロジェクト記憶索引",
        "",
        "このファイルは`session_memory.py rebuild-index`で生成する。手作業で編集しない。",
        "記憶は来歴と引継ぎの補助であり、README、ADR、設定、テストなどの正本を上書きしない。",
        "",
        "## 昇格候補",
        "",
    ]
    if candidates:
        lines.extend(
            [
                "| 候補 | 状態 | 昇格先 | 根拠数 |",
                "|---|---|---|---:|",
            ]
        )
        for metadata, path in sorted(
            candidates, key=lambda item: str(item[0].get("id", ""))
        ):
            evidence = metadata.get("evidence", [])
            evidence_count = len(evidence) if isinstance(evidence, list) else 0
            lines.append(
                f"| [{metadata.get('title', metadata.get('id', ''))}]"
                f"({_relative_link(path)}) | {metadata.get('status', '')} | "
                f"{metadata.get('target', '')} | {evidence_count} |"
            )
    else:
        lines.append("昇格候補はありません。")

    lines.extend(["", "## 変更セッション", ""])
    if sessions:
        lines.extend(
            [
                "| セッション | 状態 | タグ | 関連パス数 |",
                "|---|---|---|---:|",
            ]
        )
        for metadata, path in sorted(
            sessions, key=lambda item: str(item[0].get("created_at", "")), reverse=True
        ):
            tags = metadata.get("tags", [])
            tag_text = (
                ", ".join(str(tag) for tag in tags) if isinstance(tags, list) else ""
            )
            related_paths = metadata.get("related_paths", [])
            path_count = len(related_paths) if isinstance(related_paths, list) else 0
            lines.append(
                f"| [{metadata.get('title', metadata.get('id', ''))}]"
                f"({_relative_link(path)}) | {metadata.get('status', '')} | "
                f"{tag_text} | {path_count} |"
            )
    else:
        lines.append("変更セッションの記憶はまだありません。")
    return "\n".join(lines) + "\n"


def _write_index() -> None:
    """現在の記録からINDEX.mdを更新する。"""

    INDEX_PATH.write_text(_index_source(), encoding="utf-8")


def _string_list(metadata: dict[str, Any], key: str, path: Path) -> list[str]:
    """Frontmatterの文字列Listを検証して返す。"""

    value = metadata.get(key)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ProjectMemoryError(
            f"{key}は空でない文字列Listにしてください: {path.relative_to(PROJECT_ROOT)}"
        )
    return value


def _validate_session(metadata: dict[str, Any], path: Path) -> None:
    """Session記憶の必須Metadataを検証する。"""

    required_strings = (
        "id",
        "title",
        "status",
        "created_at",
        "base_commit",
        "final_commit",
    )
    for key in required_strings:
        if not isinstance(metadata.get(key), str) or not metadata[key]:
            raise ProjectMemoryError(
                f"{key}を空でない文字列にしてください: {path.relative_to(PROJECT_ROOT)}"
            )
    if metadata.get("type") != "session":
        raise ProjectMemoryError(f"typeはsessionです: {path.relative_to(PROJECT_ROOT)}")
    if metadata["id"] != path.stem:
        raise ProjectMemoryError(
            f"idとファイル名が一致しません: {path.relative_to(PROJECT_ROOT)}"
        )
    if metadata["status"] not in SESSION_STATUSES:
        raise ProjectMemoryError(
            f"Sessionのstatusが不正です: {path.relative_to(PROJECT_ROOT)}"
        )
    try:
        datetime.fromisoformat(metadata["created_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ProjectMemoryError(
            f"created_atはISO 8601形式です: {path.relative_to(PROJECT_ROOT)}"
        ) from error
    _string_list(metadata, "tags", path)
    related_paths = metadata.get("related_paths")
    if not isinstance(related_paths, list) or not all(
        isinstance(item, str) and item for item in related_paths
    ):
        raise ProjectMemoryError(
            f"related_pathsは文字列Listにしてください: {path.relative_to(PROJECT_ROOT)}"
        )
    for related_path in related_paths:
        candidate = Path(related_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ProjectMemoryError(
                f"related_pathsはRepository相対パスです: {path.relative_to(PROJECT_ROOT)}"
            )


def _validate_candidate(
    metadata: dict[str, Any], path: Path, session_ids: set[str]
) -> None:
    """昇格候補のLifecycleと根拠を検証する。"""

    for key in ("id", "title", "status", "target"):
        if not isinstance(metadata.get(key), str) or not metadata[key]:
            raise ProjectMemoryError(
                f"{key}を空でない文字列にしてください: {path.relative_to(PROJECT_ROOT)}"
            )
    if metadata.get("type") != "promotion-candidate":
        raise ProjectMemoryError(
            f"typeはpromotion-candidateです: {path.relative_to(PROJECT_ROOT)}"
        )
    if metadata["id"] != path.stem:
        raise ProjectMemoryError(
            f"idとファイル名が一致しません: {path.relative_to(PROJECT_ROOT)}"
        )
    if metadata["status"] not in CANDIDATE_STATUSES:
        raise ProjectMemoryError(
            f"候補のstatusが不正です: {path.relative_to(PROJECT_ROOT)}"
        )
    if metadata["target"] not in PROMOTION_TARGETS:
        raise ProjectMemoryError(
            f"候補のtargetが不正です: {path.relative_to(PROJECT_ROOT)}"
        )
    evidence = _string_list(metadata, "evidence", path)
    unknown_evidence = sorted(set(evidence) - session_ids)
    if unknown_evidence:
        raise ProjectMemoryError(
            f"存在しないSession根拠があります: {', '.join(unknown_evidence)}"
        )
    promoted_to = metadata.get("promoted_to")
    if metadata["status"] == "promoted" and not (
        isinstance(promoted_to, str) and promoted_to
    ):
        raise ProjectMemoryError(
            f"promotedではpromoted_toが必要です: {path.relative_to(PROJECT_ROOT)}"
        )


def _validate_secrets(path: Path) -> None:
    """共有記憶に明白なCredential形式がないことを確認する。"""

    source = path.read_text(encoding="utf-8")
    if any(pattern.search(source) for pattern in SECRET_PATTERNS):
        raise ProjectMemoryError(
            f"秘密情報らしい文字列を共有記憶へ保存できません: {path.relative_to(PROJECT_ROOT)}"
        )


def _validate_memory() -> None:
    """共有記憶全体のSchema、参照、索引、秘密情報を検証する。"""

    if not (MEMORY_ROOT / "README.md").is_file():
        raise ProjectMemoryError("docs/project-memory/README.mdがありません。")
    session_records = [
        (_frontmatter(path)[0], path) for path in _record_paths(SESSION_ROOT)
    ]
    candidate_records = [
        (_frontmatter(path)[0], path) for path in _record_paths(CANDIDATE_ROOT)
    ]
    identifiers: set[str] = set()
    for metadata, path in session_records:
        _validate_session(metadata, path)
        identifier = str(metadata["id"])
        if identifier in identifiers:
            raise ProjectMemoryError(f"記憶IDが重複しています: {identifier}")
        identifiers.add(identifier)
    session_ids = {str(metadata["id"]) for metadata, _ in session_records}
    for metadata, path in candidate_records:
        _validate_candidate(metadata, path, session_ids)
        identifier = str(metadata["id"])
        if identifier in identifiers:
            raise ProjectMemoryError(f"記憶IDが重複しています: {identifier}")
        identifiers.add(identifier)
    for path in sorted(MEMORY_ROOT.rglob("*.md")):
        _validate_secrets(path)
    if (
        not INDEX_PATH.is_file()
        or INDEX_PATH.read_text(encoding="utf-8") != _index_source()
    ):
        raise ProjectMemoryError(
            "INDEX.mdが現在の記憶と一致しません。rebuild-indexを実行してください。"
        )


def _yaml_frontmatter(metadata: dict[str, Any]) -> str:
    """Metadataを日本語を保持したYAML Frontmatterへ変換する。"""

    return yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).rstrip()


def _single_line(value: str) -> str:
    """CLI引数をMarkdownの1行へ正規化する。"""

    return " ".join(value.split())


def _bullets(values: list[str], default: str) -> str:
    """文字列ListをMarkdown箇条書きへ変換する。"""

    normalized = [_single_line(value) for value in values if value.strip()]
    if not normalized:
        normalized = [default]
    return "\n".join(f"- {value}" for value in normalized)


def _note_source(
    metadata: dict[str, Any],
    request: str,
    outcome: str,
    decisions: list[str],
    verifications: list[str],
    remaining: list[str],
) -> str:
    """Session記憶のMarkdownを生成する。"""

    related_paths = metadata["related_paths"]
    canonical_sources = (
        [f"`{path}`" for path in related_paths]
        if related_paths
        else ["利用者による明示的な記録依頼"]
    )
    return (
        f"---\n{_yaml_frontmatter(metadata)}\n---\n\n"
        f"# {metadata['title']}\n\n"
        f"## 利用者の依頼\n\n{_single_line(request)}\n\n"
        f"## 実装結果\n\n{_single_line(outcome)}\n\n"
        f"## 重要な判断\n\n{_bullets(decisions, '特記事項なし')}\n\n"
        f"## 検証\n\n{_bullets(verifications, '未実行')}\n\n"
        f"## 未完了事項\n\n{_bullets(remaining, 'なし')}\n\n"
        f"## 正本への参照\n\n{_bullets(canonical_sources, 'なし')}\n"
    )


def _slug(value: str) -> str:
    """記憶ファイル用の英数字Slugを検証する。"""

    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
        raise ProjectMemoryError(
            "slugは小文字英数字をHyphenで区切って指定してください。"
        )
    return normalized


def _start(args: argparse.Namespace) -> dict[str, Any]:
    """変更前のGit状態を一時Directoryへ保存する。"""

    repository_root = Path(_git_text("rev-parse", "--show-toplevel")).resolve()
    if repository_root != PROJECT_ROOT:
        raise ProjectMemoryError("Skillの配置先とGit Repository Rootが一致しません。")
    now = _now()
    session_id = args.session_id or (
        now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    )
    state = {
        "session_id": session_id,
        "repository": str(PROJECT_ROOT),
        "started_at": _format_datetime(now),
        "last_seen_at": _format_datetime(now),
        "base_commit": _git_text("rev-parse", "HEAD"),
        "snapshot": _worktree_snapshot(),
    }
    path = _state_path(session_id)
    resumed = path.exists()
    if resumed and not args.keep_existing:
        raise ProjectMemoryError(
            f"同じsession_idの開始状態が既にあります: {session_id}"
        )
    if resumed:
        state = {**_read_state(session_id), "last_seen_at": _format_datetime(now)}
    _write_json(path, state)
    other_sessions = _other_active_sessions(session_id, now)
    return {
        "session_id": session_id,
        "resumed": resumed,
        "started_at": state["started_at"],
        "base_commit": state["base_commit"],
        "preexisting_paths": sorted(state["snapshot"]),
        "other_active_sessions": other_sessions,
        "use_separate_worktree": bool(other_sessions),
    }


def _session_paths(
    state: dict[str, Any], excluded: set[str], final_commit: str
) -> list[str]:
    """開始時状態と比べ、Sessionによる有効な変更パスを返す。"""

    before = state.get("snapshot")
    if not isinstance(before, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in before.items()
    ):
        raise ProjectMemoryError("開始時Snapshotが不正です。")
    after = _worktree_snapshot()
    paths = _changed_paths(before, after, excluded)
    committed_paths = _committed_paths(str(state["base_commit"]), final_commit)
    preexisting_committed_paths = _preexisting_committed_paths(
        committed_paths, before, after
    )
    paths.difference_update(preexisting_committed_paths)
    paths.update(committed_paths - preexisting_committed_paths - excluded)
    return sorted(paths)


def _promotion_hints(tags: list[str]) -> list[dict[str, Any]]:
    """同じタグを持つ記憶が閾値に達したタグと記憶IDを返す。"""

    memory_ids: dict[str, list[str]] = {tag: [] for tag in tags}
    for path in _record_paths(SESSION_ROOT):
        metadata, _ = _frontmatter(path)
        for tag in metadata.get("tags") or []:
            if tag in memory_ids:
                memory_ids[tag].append(str(metadata["id"]))
    return [
        {"tag": tag, "memory_ids": sorted(ids)}
        for tag, ids in sorted(memory_ids.items())
        if tag != DEFAULT_SESSION_TAG and len(ids) >= PROMOTION_HINT_THRESHOLD
    ]


def _status(args: argparse.Namespace) -> dict[str, Any]:
    """未記録の変更があるかを返し、必要なら催促済みとして記録する。"""

    state_path = _state_path(args.session_id)
    if not state_path.is_file():
        return {"started": False, "pending_paths": [], "reminded": False}
    state = _read_state(args.session_id)
    pending_paths = _session_paths(state, set(), _git_text("rev-parse", "HEAD"))
    reminded = state.get("reminded") is True
    # Stop Hookが毎Turn呼ぶため、別Sessionから見た使用中の判定をここで更新する。
    updated = {**state, "last_seen_at": _format_datetime(_now())}
    if args.mark_reminded and pending_paths and not reminded:
        updated["reminded"] = True
    _write_json(state_path, updated)
    return {"started": True, "pending_paths": pending_paths, "reminded": reminded}


def _discard(args: argparse.Namespace) -> dict[str, Any]:
    """記憶を作らずに開始状態を破棄する。"""

    state_path = _state_path(args.session_id)
    if not state_path.is_file():
        return {"discarded": False}
    state_path.unlink()
    return {"discarded": True}


def _finish(args: argparse.Namespace) -> dict[str, Any]:
    """Git差分を判定し、必要なSession記憶と索引を生成する。"""

    state = _read_state(args.session_id)
    excluded = {path.replace("\\", "/") for path in args.exclude_path}
    final_commit = _git_text("rev-parse", "HEAD")
    sorted_paths = _session_paths(state, excluded, final_commit)
    state_path = _state_path(args.session_id)
    if not sorted_paths and not args.force:
        state_path.unlink()
        return {
            "recorded": False,
            "reason": "セッションによる有効なRepository変更がありません。",
            "changed_paths": [],
        }

    now = _now()
    slug = _slug(args.slug or args.session_id.lower())
    memory_id = f"{now.strftime('%Y-%m-%dT%H%M%SZ')}-{slug}"
    path = SESSION_ROOT / now.strftime("%Y") / f"{memory_id}.md"
    if path.exists():
        raise ProjectMemoryError(f"同じ記憶ファイルが既にあります: {path}")
    tags = sorted(set(args.tag or ["repository-change"]))
    metadata = {
        "type": "session",
        "id": memory_id,
        "title": _single_line(args.title),
        "status": "current",
        "created_at": _format_datetime(now),
        "base_commit": str(state["base_commit"]),
        "final_commit": final_commit,
        "tags": tags,
        "related_paths": sorted_paths,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _note_source(
            metadata,
            args.request,
            args.outcome,
            args.decision,
            args.verification,
            args.remaining,
        ),
        encoding="utf-8",
    )
    _write_index()
    _validate_memory()
    state_path.unlink()
    return {
        "recorded": True,
        "memory_id": memory_id,
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "changed_paths": sorted_paths,
        "promotion_hints": _promotion_hints(tags),
    }


def _rebuild_index(args: argparse.Namespace) -> dict[str, Any]:
    """索引を生成または検査する。"""

    expected = _index_source()
    if args.check:
        if (
            not INDEX_PATH.is_file()
            or INDEX_PATH.read_text(encoding="utf-8") != expected
        ):
            raise ProjectMemoryError("INDEX.mdが現在の記憶と一致しません。")
        return {"valid": True, "path": INDEX_PATH.relative_to(PROJECT_ROOT).as_posix()}
    INDEX_PATH.write_text(expected, encoding="utf-8")
    return {"updated": True, "path": INDEX_PATH.relative_to(PROJECT_ROOT).as_posix()}


def _validate(_args: argparse.Namespace) -> dict[str, Any]:
    """共有記憶全体を検証する。"""

    _validate_memory()
    return {
        "valid": True,
        "sessions": len(_record_paths(SESSION_ROOT)),
        "candidates": len(_record_paths(CANDIDATE_ROOT)),
    }


def create_argument_parser() -> argparse.ArgumentParser:
    """CLI引数Parserを生成する。"""

    parser = argparse.ArgumentParser(description="Project共有記憶を管理します。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="変更前のGit状態を保存する")
    start_parser.add_argument("--session-id", help="省略時は一意な識別子を生成する")
    start_parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="同じsession_idの開始状態があれば上書きせずに再利用する",
    )
    start_parser.set_defaults(handler=_start)

    status_parser = subparsers.add_parser(
        "status", help="開始時から記録されていない変更を確認する"
    )
    status_parser.add_argument("--session-id", required=True)
    status_parser.add_argument(
        "--mark-reminded",
        action="store_true",
        help="未記録の変更があれば催促済みとして開始状態へ記録する",
    )
    status_parser.set_defaults(handler=_status)

    discard_parser = subparsers.add_parser(
        "discard", help="記憶を作らずに開始状態を破棄する（worktreeへ移るときなど）"
    )
    discard_parser.add_argument("--session-id", required=True)
    discard_parser.set_defaults(handler=_discard)

    finish_parser = subparsers.add_parser(
        "finish", help="変更を判定して必要ならSession記憶を作る"
    )
    finish_parser.add_argument("--session-id", required=True)
    finish_parser.add_argument("--slug", help="記憶ファイル名用の小文字英数字Slug")
    finish_parser.add_argument("--title", required=True)
    finish_parser.add_argument("--request", required=True)
    finish_parser.add_argument("--outcome", required=True)
    finish_parser.add_argument("--decision", action="append", default=[])
    finish_parser.add_argument("--verification", action="append", default=[])
    finish_parser.add_argument("--remaining", action="append", default=[])
    finish_parser.add_argument("--tag", action="append", default=[])
    finish_parser.add_argument(
        "--exclude-path",
        action="append",
        default=[],
        help="並行作業などによる対象外のRepository相対パス",
    )
    finish_parser.add_argument(
        "--force", action="store_true", help="有効な差分がなくても明示的に記録する"
    )
    finish_parser.set_defaults(handler=_finish)

    index_parser = subparsers.add_parser("rebuild-index", help="索引を再生成する")
    index_parser.add_argument(
        "--check", action="store_true", help="書き換えず現在の索引を検証する"
    )
    index_parser.set_defaults(handler=_rebuild_index)

    validate_parser = subparsers.add_parser("validate", help="共有記憶全体を検証する")
    validate_parser.set_defaults(handler=_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    """選択された共有記憶操作を実行する。"""

    args = create_argument_parser().parse_args(argv)
    try:
        result = args.handler(args)
    except (
        OSError,
        ProjectMemoryError,
        subprocess.SubprocessError,
        yaml.YAMLError,
    ) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
