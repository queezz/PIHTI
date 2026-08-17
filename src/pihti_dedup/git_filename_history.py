"""Read-only filename archaeology across every ref in a Git repository.

Git's ``-z`` name-status form is used deliberately: paths are never shell
parsed, quoted, or split on whitespace, so non-ASCII and unusual filenames
round-trip unchanged.  The public query matches one complete basename
case-insensitively, which mirrors Inventor and Windows filename resolution.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class GitHistoryError(RuntimeError):
    """Git history could not be read safely."""


@dataclass(frozen=True)
class FilenameOccurrence:
    commit: str
    committed_at: str
    subject: str
    status: str
    path: str
    rename_destination: str | None = None


@dataclass(frozen=True)
class FilenameHistory:
    basename: str
    occurrences: tuple[FilenameOccurrence, ...]

    @property
    def found(self) -> bool:
        """Whether this basename ever appeared in reachable Git history."""

        return bool(self.occurrences)


@dataclass(frozen=True)
class _Change:
    commit: str
    status: str
    path: str
    destination: str | None = None


_HEX_OBJECT = re.compile(r"^[0-9a-fA-F]{40,64}$")
_cache_lock = threading.Lock()
_change_cache: dict[tuple[str, str], tuple[_Change, ...]] = {}
_metadata_cache: dict[tuple[str, str], tuple[str, str]] = {}


def _run_git(repo: Path, *arguments: str) -> bytes:
    command = [
        "git",
        "-c",
        "core.quotePath=false",
        "-c",
        f"safe.directory={Path(repo).resolve().as_posix()}",
        "-C",
        str(repo),
        *arguments,
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise GitHistoryError(f"could not run Git: {exc}") from exc
    if result.returncode:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise GitHistoryError(message or f"Git exited with status {result.returncode}")
    return result.stdout


def _repository_root(repo: Path) -> Path:
    supplied = Path(repo).resolve()
    raw = _run_git(supplied, "rev-parse", "--show-toplevel")
    value = raw.decode("utf-8", "surrogateescape").strip()
    if not value:
        raise GitHistoryError("Git did not report a repository root")
    return Path(value).resolve()


def _ref_state(root: Path) -> str:
    """Digest every current ref target, including HEAD, for cache invalidation."""

    return hashlib.sha256(_run_git(root, "show-ref", "--head")).hexdigest()


def _decode_path(value: bytes) -> str:
    return value.decode("utf-8", "surrogateescape")


def _parse_name_status(commit: str, payload: bytes) -> tuple[_Change, ...]:
    tokens = payload.split(b"\0")
    changes: list[_Change] = []
    cursor = 0
    while cursor < len(tokens):
        raw_status = tokens[cursor]
        cursor += 1
        if not raw_status:
            continue
        status = raw_status.decode("ascii", "replace")
        if cursor >= len(tokens) or not tokens[cursor]:
            raise GitHistoryError(f"malformed name-status output for {commit}")
        path = _decode_path(tokens[cursor])
        cursor += 1
        destination = None
        if status[:1] in {"R", "C"}:
            if cursor >= len(tokens) or not tokens[cursor]:
                raise GitHistoryError(f"malformed rename output for {commit}")
            destination = _decode_path(tokens[cursor])
            cursor += 1
        changes.append(_Change(commit, status, path, destination))
    return tuple(changes)


def _all_changes(root: Path, state: str) -> tuple[_Change, ...]:
    key = (str(root), state)
    with _cache_lock:
        cached = _change_cache.get(key)
    if cached is not None:
        return cached

    commits = [
        line.strip()
        for line in _run_git(root, "rev-list", "--all").decode("ascii").splitlines()
        if line.strip()
    ]
    changes: list[_Change] = []
    for commit in commits:
        payload = _run_git(
            root,
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-status",
            "-r",
            "-z",
            "-M",
            commit,
            "--",
        )
        changes.extend(_parse_name_status(commit, payload))
    result = tuple(changes)
    with _cache_lock:
        _change_cache[key] = result
        # Do not retain obsolete snapshots for this repository indefinitely.
        stale = [item for item in _change_cache if item[0] == str(root) and item != key]
        for item in stale:
            del _change_cache[item]
    return result


def _commit_metadata(root: Path, commit: str) -> tuple[str, str]:
    key = (str(root), commit)
    with _cache_lock:
        cached = _metadata_cache.get(key)
    if cached is not None:
        return cached
    payload = _run_git(root, "show", "-s", "--format=%cI%x00%s", commit, "--")
    fields = payload.rstrip(b"\n").split(b"\0", 1)
    if len(fields) != 2:
        raise GitHistoryError(f"malformed commit metadata for {commit}")
    result = tuple(field.decode("utf-8", "surrogateescape") for field in fields)
    with _cache_lock:
        _metadata_cache[key] = result
    return result  # type: ignore[return-value]


def query_filename_history(repo: Path, basename: str) -> FilenameHistory:
    """Return every change occurrence of one exact basename across all refs."""

    name = str(basename)
    if not name or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError("basename must be one filename, not a path")
    root = _repository_root(Path(repo))
    state = _ref_state(root)
    wanted = name.casefold()
    occurrences: list[FilenameOccurrence] = []
    for change in _all_changes(root, state):
        source_matches = PurePosixPath(change.path).name.casefold() == wanted
        destination_matches = bool(
            change.destination
            and PurePosixPath(change.destination).name.casefold() == wanted
        )
        if not source_matches and not destination_matches:
            continue
        committed_at, subject = _commit_metadata(root, change.commit)
        occurrences.append(
            FilenameOccurrence(
                commit=change.commit,
                committed_at=committed_at,
                subject=subject,
                status=change.status,
                path=change.path,
                rename_destination=(
                    change.destination if change.status.startswith("R") else None
                ),
            )
        )
    return FilenameHistory(name, tuple(occurrences))


def materialize_historical_blob(repo: Path, commit: str, path: str) -> bytes:
    """Return a historical blob without writing it anywhere.

    Only a full object id returned by this module is accepted.  The repository
    path must be relative and traversal-free, preventing either argument from
    becoming a Git option or escaping into another worktree location.
    """

    if not _HEX_OBJECT.fullmatch(commit):
        raise ValueError("commit must be a full hexadecimal object id")
    normalized = str(path).replace("\\", "/")
    parsed = PurePosixPath(normalized)
    if (
        not normalized
        or parsed.is_absolute()
        or normalized.startswith("/")
        or any(part in {"", ".", ".."} for part in parsed.parts)
        or "\x00" in normalized
    ):
        raise ValueError("path must be a traversal-free repository-relative path")
    root = _repository_root(Path(repo))
    return _run_git(root, "cat-file", "blob", f"{commit}:{parsed.as_posix()}")
