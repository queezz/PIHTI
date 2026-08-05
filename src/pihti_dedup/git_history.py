"""Read-only Git history helpers for reviewing merged student submissions."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pihti_dedup.inventory import CAD_EXTENSIONS

PULL_REQUEST_SUBJECT = re.compile(r"^Merge pull request #(\d+) from (.+)$")


@dataclass(frozen=True)
class PullRequestMerge:
    sha: str
    number: int
    branch: str
    paths: frozenset[str]
    folders: tuple[str, ...]
    added_paths: frozenset[str] = frozenset()

    @property
    def cad_files(self) -> int:
        return len(self.paths)


def _git(root: Path, *args: str, binary: bool = False) -> str | bytes | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=not binary,
            encoding=None if binary else "utf-8",
            errors=None if binary else "replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _cad_paths(output: bytes) -> frozenset[str]:
    return frozenset(
        path
        for raw in output.split(b"\0")
        if raw
        for path in [raw.decode("utf-8", errors="replace").replace("\\", "/")]
        if Path(path).suffix.casefold() in CAD_EXTENSIONS
    )


def recent_pull_request_merges(root: Path, *, limit: int = 6) -> tuple[PullRequestMerge, ...]:
    """Return recent first-parent PR merges and their surviving CAD paths."""

    history = _git(
        root,
        "log",
        "--first-parent",
        "--merges",
        f"--max-count={max(limit * 3, limit)}",
        "--format=%H%x1f%s%x1e",
    )
    if not isinstance(history, str):
        return ()

    merges: list[PullRequestMerge] = []
    for entry in history.split("\x1e"):
        entry = entry.strip()
        if not entry or "\x1f" not in entry:
            continue
        sha, subject = entry.split("\x1f", 1)
        match = PULL_REQUEST_SUBJECT.match(subject.strip())
        if not match:
            continue

        changed = _git(
            root,
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            "-z",
            f"{sha}^1",
            sha,
            "--",
            binary=True,
        )
        if not isinstance(changed, bytes):
            continue
        added = _git(
            root,
            "diff",
            "--name-only",
            "--diff-filter=A",
            "-z",
            f"{sha}^1",
            sha,
            "--",
            binary=True,
        )
        if not isinstance(added, bytes):
            continue
        paths = _cad_paths(changed)
        added_paths = _cad_paths(added)
        folders = tuple(sorted({path.split("/", 1)[0] for path in paths}, key=str.casefold))
        merges.append(
            PullRequestMerge(
                sha=sha,
                number=int(match.group(1)),
                branch=match.group(2),
                paths=paths,
                folders=folders,
                added_paths=added_paths,
            )
        )
        if len(merges) >= limit:
            break
    return tuple(merges)
