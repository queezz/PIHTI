"""Find standard fasteners outside the library and move them into it.

`PIHTI.ipj` sets `UsingUniqueFilenames=Yes` with the workspace at `.`. When a
referring assembly's stored path fails, Inventor searches the whole workspace
for the filename. Exactly one match binds silently, which is the property this
module relies on: moving a *uniquely named* part into `ContentCenter/Fastners`
changes its folder and nothing else Inventor cares about. Every assembly that
used it finds it again by name, with no dialog and no repointing.

That property holds only while the name is unique. A same-named file anywhere
else in the workspace turns the move into a collision decision, so this module
refuses it and points at Collision Doctor. The one exception is a
byte-identical copy already waiting at the destination: then nothing needs to
move, and the stray copy can go to the recoverable quarantine instead.

A candidate needs evidence, and the evidence is named in the result:

- `iproperty` — the Inventor `standard` iProperty is set, as Content Center
  writes it on every part it generates (`JIS B 1176`, `ANSI B18.3.4M`).
- `name` — the filename carries an explicit standard designation.
- `convention` — the filename follows the library's own naming exactly
  (`M3x10-SHCS.ipt`, `M3-nut.ipt`, `M4-Washer.ipt`).
- `description` — the Description iProperty names a fastener type.

Only `.ipt` files are proposed: an assembly is never a standard part, and the
collision map covers exactly the Inventor extensions. Nothing here guesses from
a loose "contains nut" match; `anode-holding-nut.ipt` is custom geometry.

A move is a plain `Path.rename` plus its sidecar. It is recorded in the rename
ledger, because a move is a rename whose folder changed. Git is untouched.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping

from pihti_dedup.cleanup import (
    CleanupCandidate,
    MemberCleanupExecution,
    execute_survivor_quarantine,
)
from pihti_dedup.inventory import sha256_file
from pihti_dedup.renames import (
    MAX_PATH_LENGTH,
    RenameEntry,
    RenameError,
    append_entry,
    check_filename,
)
from pihti_dedup.sidecar import sidecar_path
from pihti_dedup.whereused import WhereUsed, filename_locations

DEFAULT_DESTINATION = "ContentCenter/Fastners"
#: Every ledger line this module writes starts with this, so a move is
#: distinguishable from a rename without parsing paths.
MOVE_NOTE_PREFIX = "standard part → ContentCenter"
QUARANTINE_SOURCE = "standard-part"

MOVE = "move"
IDENTICAL = "already-there-identical"
CONFLICT = "conflict"
REFUSED = "refused"
OUTCOMES = (MOVE, IDENTICAL, CONFLICT, REFUSED)

#: Library root and the folders that never hold curated source: save history
#: and STEP import trees.
_EXCLUDED_ROOT = "contentcenter"
_EXCLUDED_SEGMENTS = frozenset({"oldversions", "steps"})

# Explicit designations only. A standard number never starts with 0, which is
# what keeps a KiCad footprint such as `R_Axial_DIN0617_...` out.
_DESIGNATIONS = (
    ("JIS", re.compile(r"(?<![A-Za-z])JIS\s*B\s*[1-9]\d*", re.IGNORECASE)),
    ("DIN", re.compile(r"(?<![A-Za-z])DIN\s*(?:EN\s*)?(?:ISO\s*)?[1-9]\d{2,4}(?:-\d+)?", re.IGNORECASE)),
    ("ISO", re.compile(r"(?<![A-Za-z])ISO\s*[1-9]\d{2,4}(?:-\d+)?", re.IGNORECASE)),
    ("ANSI", re.compile(r"(?<![A-Za-z])ANSI\s*B?\s*[1-9]\d*(?:\.\d+)*M?", re.IGNORECASE)),
)
_CONVENTION = (
    re.compile(
        r"^M\d+(?:\.\d+)?x\d+(?:\.\d+)?-(?:SHCS|BHCS|FHCS|HexCS|set-screw|countersunk"
        r"|Fillips-Countersink|fillips-round)\.ipt$",
        re.IGNORECASE,
    ),
    re.compile(r"^M\d+(?:\.\d+)?-nut(?:-\w+)?\.ipt$", re.IGNORECASE),
    re.compile(r"^M\d+(?:\.\d+)?-washer\.ipt$", re.IGNORECASE),
)
_DESCRIPTION = re.compile(
    r"cap screw|socket head|hexagon socket|六角穴付き|button head|set screw|washer",
    re.IGNORECASE,
)


class StandardMoveError(ValueError):
    """The move is not something this tool is willing to perform."""


@dataclass(frozen=True)
class EvidenceItem:
    kind: str
    label: str


@dataclass(frozen=True)
class StandardEvidence:
    """Why a file is proposed, one item per evidence class that fired."""

    items: tuple[EvidenceItem, ...]

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(item.kind for item in self.items)

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(item.label for item in self.items)


def _parts(path: str) -> list[str]:
    return [part for part in path.replace("\\", "/").split("/") if part]


def is_excluded_path(path: str) -> bool:
    parts = [part.casefold() for part in _parts(path)]
    if not parts:
        return True
    if parts[0] == _EXCLUDED_ROOT:
        return True
    return any(part in _EXCLUDED_SEGMENTS for part in parts[:-1])


def _designation(name: str) -> str:
    matches = [
        match.group(0)
        for _family, pattern in _DESIGNATIONS
        for match in pattern.finditer(Path(name).stem)
    ]
    if not matches:
        return ""
    longest = max(matches, key=len)
    return re.sub(r"\s+", " ", longest).strip()


def is_standard_candidate(record, fields: Mapping[str, object] | None) -> StandardEvidence | None:
    """Evidence that `record` is a standard part, or None.

    `record` needs only a workspace-relative `path`; `fields` are the flattened
    iProperties (`DocumentMeta.fields`), or None when they could not be read.
    """

    path = str(getattr(record, "path", record)).replace("\\", "/")
    name = path.rsplit("/", 1)[-1]
    if Path(name).suffix.casefold() != ".ipt" or is_excluded_path(path):
        return None
    fields = fields or {}
    items: list[EvidenceItem] = []

    standard = fields.get("standard")
    if isinstance(standard, str) and standard.strip():
        items.append(EvidenceItem("iproperty", f"iProperty standard: {standard.strip()}"))
    designation = _designation(name)
    if designation:
        items.append(EvidenceItem("name", f"name: {designation}"))
    if any(pattern.match(name) for pattern in _CONVENTION):
        items.append(EvidenceItem("convention", "Fastners convention"))
    description = fields.get("description")
    if isinstance(description, str) and _DESCRIPTION.search(description):
        items.append(EvidenceItem("description", "description"))
    return StandardEvidence(tuple(items)) if items else None


@dataclass(frozen=True)
class MovePlan:
    """One proposed move, with its outcome decided and explained."""

    outcome: str
    source_path: str
    name: str
    destination_folder: str
    destination_path: str
    size: int = 0
    mtime_ns: int = 0
    sha256: str = ""
    referrers: tuple[str, ...] = ()
    other_locations: tuple[str, ...] = ()
    survivor_path: str = ""
    survivor_size: int = 0
    survivor_mtime_ns: int = 0
    survivor_sha256: str = ""
    sidecar_from: str | None = None
    sidecar_to: str | None = None
    evidence: tuple[str, ...] = ()
    reason: str = ""

    @property
    def will_prompt(self) -> bool:
        # A unique name is found again by filename; Inventor never asks.
        return False

    @property
    def actionable(self) -> bool:
        return self.outcome in {MOVE, IDENTICAL}

    @property
    def source_folder(self) -> str:
        return self.source_path.rsplit("/", 1)[0] if "/" in self.source_path else "."

    @property
    def signature(self) -> str:
        evidence = "\0".join(
            [
                self.outcome,
                self.source_path,
                self.destination_path,
                str(self.size),
                str(self.mtime_ns),
                self.sha256,
                self.survivor_path,
                self.survivor_sha256,
            ]
        )
        return hashlib.sha256(evidence.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "source_path": self.source_path,
            "destination_path": self.destination_path,
            "name": self.name,
            "evidence": list(self.evidence),
            "referrers": list(self.referrers),
            "other_locations": list(self.other_locations),
            "survivor_path": self.survivor_path,
            "reason": self.reason,
            "signature": self.signature,
        }


@dataclass(frozen=True)
class StandardCandidate:
    path: str
    name: str
    evidence: StandardEvidence
    plan: MovePlan
    record: object = None


@dataclass
class StandardMoveResult:
    plan: MovePlan
    entry: RenameEntry | None = None
    quarantine: MemberCleanupExecution | None = None
    sidecar_moved: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _normalized_folder(folder: str) -> str:
    return "/".join(_parts(folder))


def _classify(
    source_path: str,
    destination_path: str,
    name: str,
    locations: Mapping[str, tuple[str, ...]],
) -> tuple[str, tuple[str, ...]]:
    """(outcome before hashing, other same-name paths) from the collision map."""

    others = tuple(
        path
        for path in locations.get(name.casefold(), ())
        if path.casefold() != source_path.casefold()
    )
    if not others:
        return MOVE, others
    if len(others) == 1 and others[0].casefold() == destination_path.casefold():
        return IDENTICAL, others
    return CONFLICT, others


def plan_standard_move(
    root: Path,
    relative_path: str,
    *,
    index: WhereUsed,
    locations: Mapping[str, tuple[str, ...]] | None = None,
    destination_folder: str = DEFAULT_DESTINATION,
    evidence: Iterable[str] = (),
    known_sha256: str | None = None,
) -> MovePlan:
    """Decide what moving one file into the library would do. Never moves.

    `known_sha256` lets a caller that already hashed the file (the inventory
    snapshot) skip the read; it is trusted only as far as the caller checked
    size and modification time.
    """

    root = Path(root).resolve()
    source_path = "/".join(_parts(relative_path))
    name = source_path.rsplit("/", 1)[-1]
    folder = _normalized_folder(destination_folder)
    destination_path = f"{folder}/{name}" if folder else name
    base = MovePlan(
        outcome=REFUSED,
        source_path=source_path,
        name=name,
        destination_folder=folder,
        destination_path=destination_path,
        evidence=tuple(evidence),
    )

    def refused(reason: str, **changes) -> MovePlan:
        return replace(base, **changes, outcome=REFUSED, reason=reason)

    source = root / source_path
    try:
        source.resolve().relative_to(root)
    except ValueError:
        return refused("that path is outside the workspace")
    if source.is_symlink() or not source.is_file():
        return refused("that file is no longer in the workspace")
    if source.suffix.casefold() != ".ipt":
        return refused("only Inventor parts (.ipt) are moved into the library")
    target_folder = root / folder
    try:
        target_folder.resolve().relative_to(root)
    except ValueError:
        return refused("the destination folder is outside the workspace")
    if not target_folder.is_dir():
        return refused(f"the destination folder {folder} does not exist")
    if source.parent.resolve() == target_folder.resolve():
        return refused(f"{name} is already in {folder}")

    stat = source.stat()
    sha256 = known_sha256 or sha256_file(source)
    base = replace(
        base,
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        sha256=sha256,
        referrers=index.referring(name),
    )
    try:
        check_filename(name)
    except RenameError as exc:
        return refused(str(exc))
    target = root / destination_path
    if len(str(target)) > MAX_PATH_LENGTH:
        return refused(
            f"the new path would be {len(str(target))} characters; "
            f"Inventor and Windows stop being reliable past {MAX_PATH_LENGTH}"
        )

    known = locations if locations is not None else filename_locations(root)
    outcome, others = _classify(source_path, destination_path, name, known)
    base = replace(base, other_locations=others)

    if outcome == CONFLICT:
        return replace(
            base,
            outcome=CONFLICT,
            reason=(
                f"{name} also exists at {', '.join(others)}. Moving one copy would not "
                "make the name unique; resolve the collision first."
            ),
        )

    if outcome == IDENTICAL:
        survivor = root / others[0]
        try:
            survivor_stat = survivor.stat()
            survivor_sha = sha256_file(survivor)
        except OSError as exc:
            return refused(f"cannot read the library copy: {exc}")
        if survivor_sha != sha256:
            return replace(
                base,
                outcome=CONFLICT,
                reason=(
                    f"{destination_path} already exists with different bytes. "
                    "Decide which revision stays before either moves."
                ),
            )
        return replace(
            base,
            outcome=IDENTICAL,
            survivor_path=others[0],
            survivor_size=survivor_stat.st_size,
            survivor_mtime_ns=survivor_stat.st_mtime_ns,
            survivor_sha256=survivor_sha,
            reason=f"a byte-identical copy already stands at {others[0]}",
        )

    if target.exists():
        return refused(f"{destination_path} appeared on disk; rescan and try again")
    companion = sidecar_path(source)
    sidecar_from = sidecar_to = None
    if companion.is_file():
        moved = sidecar_path(target)
        if moved.exists():
            return refused(f"{moved.name} already exists in {folder}; move or delete it first")
        sidecar_from = companion.relative_to(root).as_posix()
        sidecar_to = moved.relative_to(root).as_posix()
    return replace(base, outcome=MOVE, sidecar_from=sidecar_from, sidecar_to=sidecar_to)


def find_standard_candidates(
    root: Path,
    records: Iterable,
    *,
    fields_for: Callable[[object], Mapping[str, object] | None],
    index: WhereUsed,
    locations: Mapping[str, tuple[str, ...]],
    destination_folder: str = DEFAULT_DESTINATION,
) -> tuple[StandardCandidate, ...]:
    """Every candidate with its plan, ordered by outcome and then by path."""

    found: list[StandardCandidate] = []
    for record in records:
        path = str(record.path)
        if Path(path).suffix.casefold() != ".ipt" or is_excluded_path(path):
            continue
        evidence = is_standard_candidate(record, fields_for(record))
        if evidence is None:
            continue
        plan = plan_standard_move(
            root,
            path,
            index=index,
            locations=locations,
            destination_folder=destination_folder,
            evidence=evidence.labels,
            known_sha256=_trusted_hash(Path(root) / path, record),
        )
        found.append(StandardCandidate(path, plan.name, evidence, plan, record))
    order = {outcome: position for position, outcome in enumerate(OUTCOMES)}
    found.sort(key=lambda item: (order[item.plan.outcome], item.path.casefold()))
    return tuple(found)


def _trusted_hash(path: Path, record) -> str | None:
    digest = getattr(record, "sha256", None)
    if not digest:
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    if (stat.st_size, stat.st_mtime_ns) != (getattr(record, "size", None), getattr(record, "mtime_ns", None)):
        return None
    return digest


def _revalidate_source(root: Path, plan: MovePlan) -> Path:
    source = root / plan.source_path
    if source.is_symlink() or not source.is_file():
        raise StandardMoveError("that file is no longer in the workspace")
    stat = source.stat()
    if (
        stat.st_size != plan.size
        or stat.st_mtime_ns != plan.mtime_ns
        or sha256_file(source) != plan.sha256
    ):
        raise StandardMoveError(f"{plan.source_path} changed after review; rescan and review again")
    return source


def execute_standard_move(root: Path, plan: MovePlan, *, confirmed: bool) -> StandardMoveResult:
    """Carry out one reviewed plan. Never commits and never deletes.

    `move` renames the file (and its sidecar) into the library and appends a
    ledger line. `already-there-identical` quarantines the stray copy through
    the recoverable member-cleanup store. Everything is revalidated first: the
    source's size, modification time, and hash, and a fresh collision map.
    """

    if not confirmed:
        raise StandardMoveError("every standard-part move needs an explicit confirmation")
    if plan.outcome not in {MOVE, IDENTICAL}:
        raise StandardMoveError(plan.reason or f"{plan.outcome} plans are not executed")
    root = Path(root).resolve()
    source = _revalidate_source(root, plan)
    outcome, _others = _classify(
        plan.source_path, plan.destination_path, plan.name, filename_locations(root)
    )
    if outcome != plan.outcome:
        raise StandardMoveError(
            f"the workspace changed since review: {plan.name} is now a {outcome} case"
        )

    if plan.outcome == IDENTICAL:
        execution = execute_survivor_quarantine(
            root,
            CleanupCandidate(
                path=plan.source_path,
                name=plan.name,
                size=plan.size,
                mtime_ns=plan.mtime_ns,
                sha256=plan.sha256,
                keep_paths=(plan.survivor_path,),
            ),
            CleanupCandidate(
                path=plan.survivor_path,
                name=plan.name,
                size=plan.survivor_size,
                mtime_ns=plan.survivor_mtime_ns,
                sha256=plan.survivor_sha256,
                keep_paths=(),
            ),
            source=QUARANTINE_SOURCE,
            plan_id=plan.signature,
            references_checked=True,
            where_used=plan.referrers,
        )
        return StandardMoveResult(plan=plan, quarantine=execution)

    target = root / plan.destination_path
    if target.exists():
        raise StandardMoveError(f"{plan.destination_path} appeared before the move ran")
    if not target.parent.is_dir():
        raise StandardMoveError(f"the destination folder {plan.destination_folder} is gone")
    source.rename(target)

    sidecar_moved = False
    warnings: list[str] = []
    if plan.sidecar_from and plan.sidecar_to:
        companion = root / plan.sidecar_from
        moved = root / plan.sidecar_to
        if companion.is_file() and not moved.exists():
            try:
                companion.rename(moved)
                sidecar_moved = True
            except OSError as exc:
                warnings.append(f"the part moved but its sidecar did not: {exc}")

    note = f"{MOVE_NOTE_PREFIX}: moved into {plan.destination_folder}"
    if plan.evidence:
        note += f"; evidence: {', '.join(plan.evidence)}"
    try:
        entry = append_entry(
            root,
            RenameEntry(
                id="",
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                old_path=plan.source_path,
                new_path=plan.destination_path,
                old_name=plan.name,
                new_name=plan.name,
                where_used=plan.referrers,
                will_prompt=False,
                settled=False,
                sidecar_moved=sidecar_moved,
                notes=note,
            ),
        )
    except OSError:
        # Without its ledger line the move would be unexplained; undo it.
        if sidecar_moved:
            (root / plan.sidecar_to).rename(root / plan.sidecar_from)
        target.rename(source)
        raise
    return StandardMoveResult(
        plan=plan, entry=entry, sidecar_moved=sidecar_moved, warnings=tuple(warnings)
    )
