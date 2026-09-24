"""Rename a CAD file in place, and remember what Inventor will do about it.

`PIHTI.ipj` sets `UsingUniqueFilenames=Yes` with the workspace at `.`. When a
referring document's stored path fails, Inventor searches the whole workspace by
filename, and the outcome splits in two:

- **Zero matches.** Inventor shows the resolve-link dialog and the user pastes a
  path. Recoverable, but only if the path is at hand — which is the whole point
  of the ledger and the `/renames` page.
- **Another file with the same name exists.** Inventor binds to *that* file
  silently. No dialog, no warning, and an assembly that now consumes the wrong
  geometry. This is the dangerous case, so a rename that would leave the old
  name alive elsewhere in the workspace is refused until it is confirmed
  explicitly, with the affected assemblies named.

A rename that would *create* a new same-name collision is refused outright.

The rename is a plain filesystem rename and never touches Git. With a running
Inventor session it can also repoint the referring documents (see
`inventor_session`); the entry then records which ones were repaired. The moved
file, the saved assemblies, and the ledger line show up as ordinary changes in
the owner's own commit.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from pihti_dedup.inventor_session import NO_DESCRIPTOR, REPAIRED
from pihti_dedup.sidecar import sidecar_path
from pihti_dedup.whereused import REFERENCED_EXTENSIONS, WhereUsed, filename_locations

if TYPE_CHECKING:
    from pihti_dedup.inventor_session import RepairResult, Session

#: Only the four Inventor extensions can be renamed here, because they are
#: exactly the set the where-used index and the collision map cover. Renaming a
#: `.stp` or `.stl` carries no unique-filename consequence and would be checked
#: against a map that does not contain it, which is worse than not offering it.
RENAMEABLE_EXTENSIONS = REFERENCED_EXTENSIONS

#: Git-tracked, machine-facing, and outside `docs/` — the `.agents/` convention
#: for a durable machine record. JSONL so an append is one line and a
#: hand-inspection needs no parser.
LEDGER_RELATIVE = ".agents/rename-ledger.jsonl"

#: Inventor and Windows both start failing well before the extended-path limit,
#: and this workspace lives under Dropbox, so the classic ceiling is the real one.
MAX_PATH_LENGTH = 260

ILLEGAL_NAME_CHARS = '<>:"/\\|?*'
RESERVED_STEMS = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }
)


class RenameError(ValueError):
    """The rename is not something this tool is willing to perform."""


@dataclass(frozen=True)
class RenamePlan:
    """A validated rename, plus what Inventor will do with the old name."""

    old_path: str
    new_path: str
    old_name: str
    new_name: str
    referrers: tuple[str, ...] = ()
    old_name_survivors: tuple[str, ...] = ()
    sidecar_from: str | None = None
    sidecar_to: str | None = None

    @property
    def will_prompt(self) -> bool:
        """True when Inventor will show the resolve dialog rather than rebind."""

        return not self.old_name_survivors

    @property
    def needs_confirmation(self) -> bool:
        return bool(self.old_name_survivors)

    def to_dict(self) -> dict:
        return {
            "old_path": self.old_path,
            "new_path": self.new_path,
            "old_name": self.old_name,
            "new_name": self.new_name,
            "referrers": list(self.referrers),
            "old_name_survivors": list(self.old_name_survivors),
            "will_prompt": self.will_prompt,
        }


@dataclass(frozen=True)
class RenameEntry:
    """One ledger line: what moved, who referred to it, and whether it settled."""

    id: str
    timestamp: str
    old_path: str
    new_path: str
    old_name: str
    new_name: str
    where_used: tuple[str, ...] = ()
    will_prompt: bool = True
    settled: bool = False
    sidecar_moved: bool = False
    notes: str = ""
    #: Referrers (workspace-relative) whose references Inventor repointed to the
    #: new file, saved, and verified on reopen.
    repaired: tuple[str, ...] = ()
    #: Referrers whose matching descriptors all resolved to another file that
    #: kept the old name (or, when nothing was repaired, who never named this
    #: file at all): a `no-descriptor` outcome. Never applicable to this
    #: rename, so never "not repaired".
    not_applicable: tuple[str, ...] = ()
    repair_note: str = ""
    #: Referrers that held no descriptor for the old name at all while at least
    #: one other referrer was repaired: a top-level assembly lists a
    #: sub-assembly's components by name only indirectly, and keeps the old
    #: name in its bytes until Inventor saves it again.
    indirect: tuple[str, ...] = ()

    @property
    def fully_repaired(self) -> bool:
        """Every referrer whose reference resolved to this file was repaired.

        A referrer recorded in `not_applicable` or `indirect` was never
        pointed at this file directly and does not count against completeness.
        """

        if not self.repaired and not self.not_applicable:
            return False
        done = {
            path.casefold() for path in (*self.repaired, *self.not_applicable, *self.indirect)
        }
        return all(path.casefold() in done for path in self.where_used)

    @property
    def has_repair_record(self) -> bool:
        """The entry carries the per-referrer repair fields, not only a note."""

        return bool(self.repaired or self.not_applicable or self.indirect)

    @property
    def repair_version(self) -> str:
        """The Inventor version named in the repair note, when there is one."""

        match = re.search(r"through Inventor ([^\s:;,]+)", self.repair_note)
        return match.group(1) if match else ""

    @property
    def new_folder(self) -> str:
        return self.new_path.rsplit("/", 1)[0] if "/" in self.new_path else "."

    @property
    def is_move(self) -> bool:
        """Same filename, new folder: a standard-part move, not a rename.

        Case-only renames are refused, so an unchanged name with a changed path
        can only be a move.
        """

        return self.old_name == self.new_name and self.old_path != self.new_path

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "old_path": self.old_path,
            "new_path": self.new_path,
            "old_name": self.old_name,
            "new_name": self.new_name,
            "where_used": list(self.where_used),
            "will_prompt": self.will_prompt,
            "settled": self.settled,
            "sidecar_moved": self.sidecar_moved,
            "notes": self.notes,
            "repaired": list(self.repaired),
            "not_applicable": list(self.not_applicable),
            "repair_note": self.repair_note,
            "indirect": list(self.indirect),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> RenameEntry:
        return cls(
            id=str(payload.get("id", "")),
            timestamp=str(payload.get("timestamp", "")),
            old_path=str(payload.get("old_path", "")),
            new_path=str(payload.get("new_path", "")),
            old_name=str(payload.get("old_name", "")),
            new_name=str(payload.get("new_name", "")),
            where_used=tuple(str(item) for item in payload.get("where_used") or ()),
            will_prompt=bool(payload.get("will_prompt", True)),
            settled=bool(payload.get("settled", False)),
            sidecar_moved=bool(payload.get("sidecar_moved", False)),
            notes=str(payload.get("notes", "")),
            repaired=tuple(str(item) for item in payload.get("repaired") or ()),
            not_applicable=tuple(str(item) for item in payload.get("not_applicable") or ()),
            repair_note=str(payload.get("repair_note", "")),
            indirect=tuple(str(item) for item in payload.get("indirect") or ()),
        )


@dataclass
class RenameResult:
    plan: RenamePlan
    entry: RenameEntry
    sidecar_moved: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)
    repair: RepairResult | None = None


def check_filename(candidate: str) -> None:
    """Refuse a filename Windows or Inventor cannot hold reliably.

    Shared by rename and by the standard-part move, which keeps the name but
    still lands it in a new folder under the same rules.
    """

    stem = Path(candidate).stem
    if not stem:
        raise RenameError("the filename needs a name before the extension")
    illegal = sorted({char for char in candidate if char in ILLEGAL_NAME_CHARS or ord(char) < 0x20})
    if illegal:
        shown = " ".join(repr(char) for char in illegal)
        raise RenameError(f"a filename cannot contain {shown}")
    if stem.casefold() in RESERVED_STEMS:
        raise RenameError(f"{stem} is a reserved Windows device name")


def _validate_new_name(new_name: str, old_name: str) -> str:
    """Return the vetted new filename, with the original extension enforced."""

    candidate = (new_name or "").strip().strip('"')
    if not candidate:
        raise RenameError("a new filename is required")
    if candidate in {".", ".."} or candidate.endswith("."):
        raise RenameError("that is not a usable filename")
    suffix = Path(old_name).suffix
    typed_suffix = Path(candidate).suffix
    if not typed_suffix:
        candidate += suffix
    elif typed_suffix.casefold() != suffix.casefold():
        raise RenameError(
            f"the extension is fixed: {old_name} must stay {suffix}, not {typed_suffix}"
        )
    check_filename(candidate)
    if candidate.casefold() == old_name.casefold():
        raise RenameError(
            "that is the same filename. Inventor matches filenames case-insensitively, "
            "so a case-only change resolves identically and is not worth a ledger entry."
        )
    return candidate


def plan_rename(
    root: Path,
    relative_path: str,
    new_name: str,
    *,
    index: WhereUsed,
    locations: dict[str, tuple[str, ...]] | None = None,
) -> RenamePlan:
    """Validate a rename against the whole workspace before anything moves."""

    root = Path(root).resolve()
    old_relative = relative_path.replace("\\", "/").strip("/")
    source = root / old_relative
    if not source.is_file():
        raise RenameError("that file is no longer in the workspace")
    if source.suffix.casefold() not in RENAMEABLE_EXTENSIONS:
        allowed = ", ".join(sorted(RENAMEABLE_EXTENSIONS))
        raise RenameError(f"only Inventor documents can be renamed here ({allowed})")
    old_name = source.name
    candidate = _validate_new_name(new_name, old_name)
    target = source.with_name(candidate)
    new_relative = target.relative_to(root).as_posix()

    if len(str(target)) > MAX_PATH_LENGTH:
        raise RenameError(
            f"the new path would be {len(str(target))} characters; "
            f"Inventor and Windows stop being reliable past {MAX_PATH_LENGTH}"
        )

    known = locations if locations is not None else filename_locations(root)
    taken = tuple(path for path in known.get(candidate.casefold(), ()) if path != old_relative)
    if taken:
        raise RenameError(
            f"{candidate} already exists in the workspace ({', '.join(taken)}). "
            "Renaming onto it would create a fresh unique-filename collision."
        )
    survivors = tuple(path for path in known.get(old_name.casefold(), ()) if path != old_relative)

    companion = sidecar_path(source)
    sidecar_from = None
    sidecar_to = None
    if companion.is_file():
        moved = sidecar_path(target)
        if moved.exists():
            raise RenameError(f"{moved.name} already exists; move or delete it first")
        sidecar_from = companion.relative_to(root).as_posix()
        sidecar_to = moved.relative_to(root).as_posix()

    return RenamePlan(
        old_path=old_relative,
        new_path=new_relative,
        old_name=old_name,
        new_name=candidate,
        referrers=index.referring(old_name),
        old_name_survivors=survivors,
        sidecar_from=sidecar_from,
        sidecar_to=sidecar_to,
    )


def execute_rename(
    root: Path,
    plan: RenamePlan,
    *,
    confirmed: bool = False,
    session: Session | None = None,
    timeout: float | None = None,
) -> RenameResult:
    """Perform a planned rename and append the ledger entry. Never commits.

    With an Inventor `session` and at least one referrer, the referrers are
    opened before the rename and repointed, saved, and verified after it
    (`inventor_session.repair_references`). The entry is settled, and Inventor
    no longer needs to ask, only when every referrer was repaired.
    """

    if plan.needs_confirmation and not confirmed:
        raise RenameError(
            f"{plan.old_name} still exists elsewhere in the workspace; "
            "Inventor would rebind to it silently. Confirm explicitly to proceed."
        )
    root = Path(root).resolve()
    source = root / plan.old_path
    target = root / plan.new_path
    if not source.is_file():
        raise RenameError("that file is no longer in the workspace")
    if target.exists():
        raise RenameError(f"{plan.new_name} appeared before the rename ran; rescan and try again")

    repair = None
    if session is not None and plan.referrers:
        repair = _rename_with_repair(root, plan, source, target, session, timeout)
    else:
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
                warnings.append(f"the CAD file moved but its sidecar did not: {exc}")

    repaired: tuple[str, ...] = ()
    not_applicable: tuple[str, ...] = ()
    indirect: tuple[str, ...] = ()
    repair_note = ""
    will_prompt = plan.will_prompt
    settled = False
    if repair is not None:
        repaired, not_applicable, indirect, repair_note = _repair_summary(root, plan, repair)
        if repair.complete:
            will_prompt = False
            settled = True

    entry = append_entry(
        root,
        RenameEntry(
            id="",
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            old_path=plan.old_path,
            new_path=plan.new_path,
            old_name=plan.old_name,
            new_name=plan.new_name,
            where_used=plan.referrers,
            will_prompt=will_prompt,
            settled=settled,
            sidecar_moved=sidecar_moved,
            repaired=repaired,
            not_applicable=not_applicable,
            repair_note=repair_note,
            indirect=indirect,
        ),
    )
    return RenameResult(
        plan=plan,
        entry=entry,
        sidecar_moved=sidecar_moved,
        warnings=tuple(warnings),
        repair=repair,
    )


def _rename_with_repair(
    root: Path,
    plan: RenamePlan,
    source: Path,
    target: Path,
    session: Session,
    timeout: float | None,
) -> RepairResult:
    from pihti_dedup.inventor_session import (
        DEFAULT_TIMEOUT,
        NO_ANSWER,
        RepairRefused,
        repair_references,
    )

    try:
        repair = repair_references(
            session,
            [root / referrer for referrer in plan.referrers],
            plan.old_name,
            target,
            rename=lambda: source.rename(target),
            survivors=[root / survivor for survivor in plan.old_name_survivors],
            timeout=DEFAULT_TIMEOUT if timeout is None else timeout,
        )
    except RepairRefused as exc:
        raise RenameError(f"{exc}; nothing was renamed") from None
    except OSError:
        raise
    except Exception as exc:  # noqa: BLE001 - a COM failure before the rename
        raise RenameError(f"Inventor refused the repair ({exc}); nothing was renamed") from None
    if not repair.renamed:
        raise RenameError(f"{NO_ANSWER}; nothing was renamed")
    return repair


def _outcome_words(root: Path, outcome: str) -> str:
    """A failed referrer's outcome as the ledger note says it to a person.

    `no-descriptor` is not a failure (see `_repair_summary`) and is never
    passed here.
    """

    words = {
        "skipped-open-in-inventor": "open in Inventor: close it first",
    }
    return words.get(outcome) or _portable(root, outcome)


def _portable(root: Path, text: str) -> str:
    """Strip this machine's workspace root from an Inventor message for the ledger."""

    for form in {str(root), root.as_posix()}:
        text = re.sub(re.escape(form) + r"[\\/]?", "", text, flags=re.IGNORECASE)
    return text


def indirect_clause(paths) -> str:
    """The sentence for referrers that hold the old name only indirectly."""

    paths = list(paths)
    if len(paths) == 1:
        return (
            f"{paths[0]} holds the old name only indirectly; "
            "Inventor refreshes it on the next save"
        )
    return (
        f"{', '.join(paths)} hold the old name only indirectly; "
        "Inventor refreshes them on the next save"
    )


def _repair_summary(
    root: Path, plan: RenamePlan, repair: RepairResult
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], str]:
    """Workspace-relative repaired, not-applicable and indirect referrers, and a note.

    A `no-descriptor` referrer held no descriptor that resolved to this file,
    so it is never folded into "not repaired". When its old-name descriptors
    resolved to another file that kept the name, it is `not_applicable` (it
    uses that other file). When it held no old-name descriptor at all while
    another referrer was repaired, it is `indirect`: a top-level assembly
    that reaches the file through a sub-assembly and keeps the old name in
    its bytes until Inventor saves it again.
    """

    by_absolute = {str(root / referrer): referrer for referrer in plan.referrers}
    elsewhere = {str(path) for path in repair.elsewhere}
    repaired: list[str] = []
    no_descriptor: list[tuple[str, bool]] = []
    missed: list[str] = []
    for path, outcome in repair.outcomes:
        relative = by_absolute.get(str(path), str(path))
        if outcome == REPAIRED:
            repaired.append(relative)
        elif outcome == NO_DESCRIPTOR:
            no_descriptor.append((relative, str(path) in elsewhere))
        else:
            missed.append(f"{relative} ({_outcome_words(root, outcome)})")
    indirect = [relative for relative, other in no_descriptor if repaired and not other]
    not_applicable = [relative for relative, _other in no_descriptor if relative not in indirect]
    where = f"Inventor {repair.version}".strip()

    extra: list[str] = []
    if not_applicable:
        extra.append(f"use another file with this name: {', '.join(not_applicable)}")
    if indirect:
        extra.append(indirect_clause(indirect))

    if not missed:
        # Nothing failed: every referrer was repaired, was never applicable,
        # or holds the name only indirectly. The repaired names are the
        # caller's to add (the toast names them again), so this sentence does
        # not list them itself.
        clauses = [f"repaired through {where}" if repaired else f"nothing to repair through {where}"]
        note = "; ".join([*clauses, *extra])
        return tuple(repaired), tuple(not_applicable), tuple(indirect), note

    if repaired:
        note = f"repaired through {where}: {', '.join(repaired)}; not repaired: {'; '.join(missed)}"
    else:
        note = f"not repaired through {where}: {'; '.join(missed)}"
    note = "; ".join([note, *extra])
    return tuple(repaired), tuple(not_applicable), tuple(indirect), note


def settled_pairs(entries) -> frozenset[tuple[str, str]]:
    """`(referrer, old name)` pairs the where-used index should no longer show.

    A repaired referrer keeps the old name only as a fossil string in its saved
    bytes; an indirect referrer keeps it until Inventor saves it again. In both
    cases the name no longer describes what the document uses.
    """

    return frozenset(
        (referrer, entry.old_name)
        for entry in entries
        for referrer in (*entry.repaired, *entry.indirect)
    )


def ledger_path(root: Path) -> Path:
    return Path(root) / LEDGER_RELATIVE


def entry_id(timestamp: str, old_path: str) -> str:
    return hashlib.sha256(f"{timestamp}\0{old_path}".encode("utf-8")).hexdigest()[:16]


def append_entry(root: Path, entry: RenameEntry) -> RenameEntry:
    """Append one JSONL line. The ledger is the only durable rename record."""

    stamped = entry if entry.id else replace(entry, id=entry_id(entry.timestamp, entry.old_path))
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(stamped.to_dict(), ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
    return stamped


def read_ledger(root: Path) -> tuple[RenameEntry, ...]:
    """Read every ledger entry, newest last. Unparsable lines are skipped.

    A hand-edited ledger should degrade to "that line is not shown", never to a
    page that will not render.
    """

    path = ledger_path(root)
    if not path.is_file():
        return ()
    entries: list[RenameEntry] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("old_path"):
            entries.append(RenameEntry.from_dict(payload))
    return tuple(entries)


def set_settled(root: Path, target_id: str, settled: bool) -> RenameEntry:
    """Flip one entry's settled flag and rewrite the ledger."""

    entries = read_ledger(root)
    match = next((entry for entry in entries if entry.id == target_id), None)
    if match is None:
        raise RenameError("that rename is not in the ledger")
    updated = replace(match, settled=bool(settled))
    path = ledger_path(root)
    lines = [
        json.dumps(
            (updated if entry.id == target_id else entry).to_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )
        for entry in entries
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return updated
