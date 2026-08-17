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


@dataclass(frozen=True)
class ConsolidationPlan:
    """Owner-reviewed consolidation of different-byte same-name revisions."""

    group_id: str
    keeper: CleanupCandidate
    candidates: tuple[CleanupCandidate, ...]

    @property
    def keep_path(self) -> str:
        return self.keeper.path

    @property
    def signature(self) -> str:
        evidence = [
            self.group_id,
            f"{self.keeper.path}\0{self.keeper.sha256}\0"
            f"{self.keeper.size}\0{self.keeper.mtime_ns}",
        ]
        evidence.extend(
            f"{item.path}\0{item.sha256}\0{item.size}\0{item.mtime_ns}"
            for item in self.candidates
        )
        return hashlib.sha256("\n".join(evidence).encode("utf-8")).hexdigest()


def plan_consolidation(
    inventory: Inventory, *, group_id: str, keep_path: str
) -> ConsolidationPlan:
    """Keep one manually chosen collision member and quarantine every other one."""

    group = next((item for item in inventory.groups if item.id == group_id), None)
    if group is None:
        raise ValueError("duplicate group was not found")
    if group.kind != "collision":
        raise ValueError("manual consolidation is only for different-byte collisions")
    keeper = next(
        (item for item in group.records if item.path.casefold() == keep_path.casefold()), None
    )
    if keeper is None:
        raise ValueError("chosen survivor was not found in the duplicate group")
    candidates = tuple(
        CleanupCandidate(
            path=item.path,
            name=item.name,
            size=item.size,
            mtime_ns=item.mtime_ns,
            sha256=item.sha256 or "",
            keep_paths=(keeper.path,),
        )
        for item in group.records
        if item.path.casefold() != keeper.path.casefold()
    )
    if not candidates or any(not item.sha256 for item in candidates):
        raise ValueError("collision members must be hashed before consolidation")
    keep_evidence = CleanupCandidate(
        path=keeper.path,
        name=keeper.name,
        size=keeper.size,
        mtime_ns=keeper.mtime_ns,
        sha256=keeper.sha256 or "",
        keep_paths=(),
    )
    if not keep_evidence.sha256:
        raise ValueError("chosen survivor must be hashed before consolidation")
    return ConsolidationPlan(group.id, keep_evidence, candidates)


def plan_member_cleanup(
    inventory: Inventory, *, group_id: str, path: str, allow_collision: bool = False
) -> MemberCleanupPlan:
    """Plan one member quarantine while preserving every other group member."""

    group = next((item for item in inventory.groups if item.id == group_id), None)
    if group is None:
        raise ValueError("duplicate group was not found")
    supported = {"exact", "renamed", "collision"} if allow_collision else {"exact", "renamed"}
    if group.kind not in supported:
        raise ValueError("different-byte collisions require explicit revision review")
    target = next(
        (record for record in group.records if record.path.casefold() == path.casefold()),
        None,
    )
    if target is None or not target.sha256:
        raise ValueError("cleanup member was not found in the duplicate group")
    survivors = [
        record
        for record in group.records
        if record.path.casefold() != target.path.casefold()
        and (group.kind == "collision" or record.sha256 == target.sha256)
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
    where_used: tuple[str, ...] = (),
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
            "where_used": list(where_used),
        },
        now=now,
    )
    return MemberCleanupExecution(plan.group_id, quarantine, manifest, moved)


def execute_consolidation(
    workspace: Path,
    plan: ConsolidationPlan,
    *,
    references_checked: bool,
    where_used: tuple[str, ...] = (),
    now: datetime | None = None,
) -> MemberCleanupExecution:
    """Quarantine every non-survivor from an explicitly reviewed collision."""

    if not references_checked:
        raise ValueError("Inventor references and revisions must be checked first")
    _validate_candidate(workspace.resolve(), plan.keeper, label="chosen survivor")
    quarantine, manifest, moved = _quarantine_candidates(
        workspace,
        plan.candidates,
        suffix=f"consolidation-{plan.group_id[:8]}",
        plan_signature=plan.signature,
        metadata={
            "action": "quarantine",
            "source": "manual-consolidation",
            "group_id": plan.group_id,
            "keep_path": plan.keep_path,
            "where_used": list(where_used),
        },
        now=now,
    )
    event = {
        "created_at": (now or datetime.now(timezone.utc)).isoformat(),
        "action": "manual-consolidation",
        "group_id": plan.group_id,
        "keep_path": plan.keep_path,
        "keep_sha256": plan.keeper.sha256,
        "removed_paths": list(moved),
        "where_used": list(where_used),
        "manifest": manifest,
    }
    ledger = workspace.resolve() / ".agents" / "consolidation-ledger.jsonl"
    try:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        restore_quarantine_manifest(workspace, manifest)
        raise
    return MemberCleanupExecution(plan.group_id, quarantine, manifest, moved)


def _validate_candidate(root: Path, candidate: CleanupCandidate, *, label: str) -> None:
    path = root / candidate.path
    if path.is_symlink():
        raise ValueError(f"{label} is a symbolic link: {candidate.path}")
    resolved = path.resolve()
    resolved.relative_to(root)
    if not resolved.is_file():
        raise ValueError(f"{label} is missing: {candidate.path}")
    stat = resolved.stat()
    if (
        stat.st_size != candidate.size
        or stat.st_mtime_ns != candidate.mtime_ns
        or sha256_file(resolved) != candidate.sha256
    ):
        raise ValueError(f"{label} changed after review: {candidate.path}")


def read_quarantine_manifests(workspace: Path) -> tuple[dict, ...]:
    """Read recoverable cleanup history newest-first; ignore damaged records."""

    root = workspace.resolve()
    bases = (
        root.parent / f"{root.name}-quarantine" / "runs",
        root / ".pihti-dedup" / "quarantine",
    )
    records: list[dict] = []
    for base in bases:
        if not base.is_dir():
            continue
        for path in base.glob("*/manifest.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["manifest"] = str(path)
                records.append(payload)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
    return tuple(sorted(records, key=lambda item: str(item.get("created_at", "")), reverse=True))


def restore_quarantine_manifest(workspace: Path, manifest_relative: str) -> tuple[str, ...]:
    """Restore every file in one manifest after exact containment/hash checks."""

    root = workspace.resolve()
    bases = (
        (root.parent / f"{root.name}-quarantine" / "runs").resolve(),
        (root / ".pihti-dedup" / "quarantine").resolve(),
    )
    supplied = Path(manifest_relative)
    manifest = (supplied if supplied.is_absolute() else root / supplied).resolve()
    if not any(manifest.is_relative_to(base) for base in bases):
        raise ValueError("restoration manifest is outside the quarantine stores")
    if manifest.name != "manifest.json" or not manifest.is_file():
        raise ValueError("restoration manifest was not found")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("restored_at"):
        raise ValueError("this quarantine manifest has already been restored")
    transfers: list[tuple[Path, Path, dict]] = []
    for item in payload.get("files", []):
        quarantine_path = str(item["quarantine_path"])
        if quarantine_path.startswith(".pihti-dedup/"):
            source = (root / quarantine_path).resolve()
        else:
            source = (manifest.parent / quarantine_path).resolve()
            source.relative_to(manifest.parent)
        destination = (root / str(item["path"])).resolve()
        destination.relative_to(root)
        if destination.exists():
            raise ValueError(f"restore destination already exists: {item['path']}")
        if not source.is_file() or sha256_file(source) != item["sha256"]:
            raise ValueError(f"quarantined file is missing or changed: {item['path']}")
        transfers.append((source, destination, item))
    moved: list[tuple[Path, Path]] = []
    try:
        for source, destination, _item in transfers:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append((source, destination))
            for companion_name in _item.get("companions", []):
                companion_source = (manifest.parent / companion_name).resolve()
                companion_source.relative_to(manifest.parent)
                companion_destination = destination.with_name(destination.name + ".md")
                if companion_destination.exists():
                    raise ValueError(
                        f"restore companion already exists: {companion_destination.name}"
                    )
                shutil.move(str(companion_source), str(companion_destination))
                moved.append((companion_source, companion_destination))
        payload["restored_at"] = datetime.now(timezone.utc).isoformat()
        manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        for source, destination in reversed(moved):
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
        raise
    return tuple(str(item["path"]) for _, _, item in transfers)


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
    store = (root.parent / f"{root.name}-quarantine" / "runs").resolve()
    quarantine_root = (store / f"{stamp}-{suffix}").resolve()
    quarantine_root.relative_to(store)

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
    moved_companions: list[tuple[Path, Path]] = []
    manifest_path = quarantine_root / "manifest.json"
    try:
        for source, destination, candidate in transfers:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append((source, destination, candidate))
            companion = source.with_name(source.name + ".md")
            if companion.is_file():
                companion_destination = destination.with_name(destination.name + ".md")
                shutil.move(str(companion), str(companion_destination))
                moved_companions.append((companion, companion_destination))
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
                    "quarantine_path": destination.relative_to(quarantine_root).as_posix(),
                    "companions": (
                        [
                            destination.with_name(destination.name + ".md")
                            .relative_to(quarantine_root)
                            .as_posix()
                        ]
                        if destination.with_name(destination.name + ".md").is_file()
                        else []
                    ),
                }
                for _, destination, candidate in moved
            ],
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except Exception:
        for source, destination in reversed(moved_companions):
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
        for source, destination, _candidate in reversed(moved):
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
        raise

    return (
        str(quarantine_root),
        str(manifest_path),
        tuple(candidate.path for _, _, candidate in moved),
    )
