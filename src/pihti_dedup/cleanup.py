"""Evidence-only cleanup plans for exact copies added by merged PRs."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from pihti_dedup.git_history import PullRequestMerge
from pihti_dedup.inventory import Inventory, sha256_file


@dataclass(frozen=True)
class CleanupCandidate:
    path: str
    name: str
    size: int
    mtime_ns: int
    sha256: str
    keep_paths: tuple[str, ...]


@dataclass(frozen=True)
class MergeCleanupPlan:
    pr_number: int
    branch: str
    merge_sha: str
    candidates: tuple[CleanupCandidate, ...]
    protected_groups: int

    @property
    def candidate_bytes(self) -> int:
        return sum(candidate.size for candidate in self.candidates)

    @property
    def signature(self) -> str:
        evidence = [self.merge_sha]
        evidence.extend(
            f"{candidate.path}\0{candidate.sha256}\0{candidate.size}\0{candidate.mtime_ns}"
            for candidate in self.candidates
        )
        return hashlib.sha256("\n".join(evidence).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "dry_run": True,
            "pr_number": self.pr_number,
            "branch": self.branch,
            "merge_sha": self.merge_sha,
            "signature": self.signature,
            "summary": {
                "candidates": len(self.candidates),
                "candidate_bytes": self.candidate_bytes,
                "protected_groups": self.protected_groups,
            },
            "candidates": [asdict(candidate) for candidate in self.candidates],
        }


@dataclass(frozen=True)
class CleanupExecution:
    pr_number: int
    quarantine: str | None
    manifest: str | None
    moved: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MemberCleanupExecution:
    group_id: str
    quarantine: str
    manifest: str
    moved: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def plan_merge_exact_cleanup(inventory: Inventory, merge: PullRequestMerge) -> MergeCleanupPlan:
    """Plan removal of merge-added exact copies while preserving an outside copy."""

    added = {path.casefold() for path in merge.added_paths}
    candidates: list[CleanupCandidate] = []
    protected_groups = 0
    for group in inventory.filename_groups:
        if group.kind != "exact":
            continue
        added_records = [record for record in group.records if record.path.casefold() in added]
        if not added_records:
            continue
        survivors = [record for record in group.records if record.path.casefold() not in added]
        if not survivors:
            protected_groups += 1
            continue
        keep_paths = tuple(record.path for record in survivors)
        candidates.extend(
            CleanupCandidate(
                path=record.path,
                name=record.name,
                size=record.size,
                mtime_ns=record.mtime_ns,
                sha256=record.sha256 or "",
                keep_paths=keep_paths,
            )
            for record in added_records
        )

    candidates.sort(key=lambda candidate: candidate.path.casefold())
    return MergeCleanupPlan(
        pr_number=merge.number,
        branch=merge.branch,
        merge_sha=merge.sha,
        candidates=tuple(candidates),
        protected_groups=protected_groups,
    )


@dataclass(frozen=True)
class MemberCleanupPlan:
    group_id: str
    group_kind: str
    candidate: CleanupCandidate

    @property
    def signature(self) -> str:
        evidence = (
            f"{self.group_id}\0{self.group_kind}\0{self.candidate.path}\0"
            f"{self.candidate.sha256}\0{self.candidate.size}\0{self.candidate.mtime_ns}"
        )
        return hashlib.sha256(evidence.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "dry_run": True,
            "group_id": self.group_id,
            "group_kind": self.group_kind,
            "signature": self.signature,
            "candidate": asdict(self.candidate),
        }


def plan_member_cleanup(inventory: Inventory, *, group_id: str, path: str) -> MemberCleanupPlan:
    """Plan one exact-byte member quarantine while preserving another copy."""

    group = next((item for item in inventory.groups if item.id == group_id), None)
    if group is None:
        raise ValueError("duplicate group was not found")
    if group.kind not in {"exact", "renamed"}:
        raise ValueError("only byte-identical groups support member cleanup")
    target = next(
        (record for record in group.records if record.path.casefold() == path.casefold()),
        None,
    )
    if target is None or not target.sha256:
        raise ValueError("cleanup member was not found in the duplicate group")
    survivors = [
        record
        for record in group.records
        if record.path.casefold() != target.path.casefold() and record.sha256 == target.sha256
    ]
    if not survivors:
        raise ValueError("cleanup would remove the last byte-identical copy")
    return MemberCleanupPlan(
        group_id=group.id,
        group_kind=group.kind,
        candidate=CleanupCandidate(
            path=target.path,
            name=target.name,
            size=target.size,
            mtime_ns=target.mtime_ns,
            sha256=target.sha256,
            keep_paths=tuple(record.path for record in survivors),
        ),
    )


def execute_cleanup(
    workspace: Path,
    plan: MergeCleanupPlan,
    *,
    references_checked: bool,
    now: datetime | None = None,
) -> CleanupExecution:
    """Move a validated plan into recoverable quarantine and write its manifest."""

    if not references_checked:
        raise ValueError("Inventor references must be checked before applying a cleanup plan")
    if not plan.candidates:
        return CleanupExecution(plan.pr_number, None, None, ())

    quarantine, manifest, moved = _quarantine_candidates(
        workspace,
        plan.candidates,
        suffix=f"pr-{plan.pr_number}",
        plan_signature=plan.signature,
        metadata={
            "action": "quarantine",
            "source": "merged-pr",
            "pr_number": plan.pr_number,
            "branch": plan.branch,
            "merge_sha": plan.merge_sha,
        },
        now=now,
    )

    return CleanupExecution(
        pr_number=plan.pr_number,
        quarantine=quarantine,
        manifest=manifest,
        moved=moved,
    )


def execute_member_cleanup(
    workspace: Path,
    plan: MemberCleanupPlan,
    *,
    references_checked: bool,
    now: datetime | None = None,
) -> MemberCleanupExecution:
    """Quarantine one explicitly selected exact-byte member."""

    if not references_checked:
        raise ValueError("Inventor references must be checked before deleting a member")
    quarantine, manifest, moved = _quarantine_candidates(
        workspace,
        (plan.candidate,),
        suffix=f"member-{plan.group_id[:8]}",
        plan_signature=plan.signature,
        metadata={
            "action": "quarantine",
            "source": "manual-member",
            "group_id": plan.group_id,
            "group_kind": plan.group_kind,
        },
        now=now,
    )
    return MemberCleanupExecution(plan.group_id, quarantine, manifest, moved)


def _quarantine_candidates(
    workspace: Path,
    candidates: tuple[CleanupCandidate, ...],
    *,
    suffix: str,
    plan_signature: str,
    metadata: dict,
    now: datetime | None,
) -> tuple[str, str, tuple[str, ...]]:
    root = workspace.resolve()
    event_time = now or datetime.now(timezone.utc)
    stamp = event_time.strftime("%Y%m%dT%H%M%SZ")
    quarantine_root = (root / ".pihti-dedup" / "quarantine" / f"{stamp}-{suffix}").resolve()
    quarantine_root.relative_to(root)

    transfers: list[tuple[Path, Path, CleanupCandidate]] = []
    for candidate in candidates:
        source_path = root / candidate.path
        if source_path.is_symlink():
            raise ValueError(f"cleanup candidate is a symbolic link: {candidate.path}")
        source = source_path.resolve()
        source.relative_to(root)
        if not source.is_file():
            raise ValueError(
                f"cleanup candidate is missing or not a regular file: {candidate.path}"
            )
        stat = source.stat()
        if (
            stat.st_size != candidate.size
            or stat.st_mtime_ns != candidate.mtime_ns
            or sha256_file(source) != candidate.sha256
        ):
            raise ValueError(f"cleanup candidate changed after preview: {candidate.path}")
        destination = (quarantine_root / candidate.path).resolve()
        destination.relative_to(quarantine_root)
        if destination.exists():
            raise ValueError(f"quarantine destination already exists: {candidate.path}")
        transfers.append((source, destination, candidate))

    moved: list[tuple[Path, Path, CleanupCandidate]] = []
    manifest_path = quarantine_root / "manifest.json"
    try:
        for source, destination, candidate in transfers:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append((source, destination, candidate))
        manifest = {
            **metadata,
            "created_at": event_time.isoformat(),
            "workspace": ".",
            "plan_signature": plan_signature,
            "references_checked": True,
            "post_apply_required": (
                "Open affected top-level assemblies in Inventor and verify resolution"
            ),
            "files": [
                {
                    **asdict(candidate),
                    "quarantine_path": destination.relative_to(root).as_posix(),
                }
                for _, destination, candidate in moved
            ],
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except Exception:
        for source, destination, _candidate in reversed(moved):
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
        raise

    return (
        quarantine_root.relative_to(root).as_posix(),
        manifest_path.relative_to(root).as_posix(),
        tuple(candidate.path for _, _, candidate in moved),
    )
