"""A STEP copy of every Inventor part and assembly, kept beside the workspace.

Nothing outside Autodesk reads `.ipt` or `.iam` geometry, so the viewer's 3D
view and anyone without Inventor need another format. The mirror is that
format: one STEP file per Inventor document, exported by Inventor itself
through the running session (`inventor_session.export_copy`).

Where it lives: the `PIHTI_DEDUP_STEP_MIRROR` environment variable when it is
set, otherwise the sibling folder `<workspace name>-step` beside the workspace
(`PIHTI-step` beside `PIHTI`). Outside the workspace, so the catalog, the
unique-filename search, and git never see it; inside Dropbox, so every machine
gets the copies without exporting them again. It is regenerable, not curated
source.

Inside it the workspace tree is mirrored one to one. Each STEP is named after
its source with `.step` appended (`Body.ipt` -> `Body.ipt.step`): a part and an
assembly may share a stem in one folder (`lp-box.ipt` and `lp-box.iam`), and
the full name keeps the two apart. Only `.ipt` and `.iam` files in the default
scan scope are mirrored: not `OldVersions/`, vendor trees, `staging/`, or an
interrupted save's `.newVer` leftover.

A STEP is current when `mirror-index.json` at the mirror root records the
source's size and modification time (to within two seconds, the rounding a
sync or a copy can introduce) for it and the STEP exists; without an index
entry, when the STEP's modification time is at or after the source's. The
mirror folder and its `README.md` are created on the first export, never on
import or when the viewer starts.

An assembly is never opened when Inventor would stop to ask about it. Before
an `.iam` is exported, every part, assembly, or presentation name the
where-used byte scan finds in it is looked up in the workspace's filename map:
a name with two or more files raises Non-Unique Project File Names, the old
name of a rename the ledger still holds open raises Resolve Link, and either
blocks Inventor until someone clicks. Such an assembly is `needs-doctor`
instead of opened (`blocking_reference`). Names the rename ledger records as
repaired or indirect for that assembly are fossil strings and are not looked
up, and a missing name the ledger does not know is not a skip: the scan finds
such names in every assembly (the template it was started from, the source
name of an imported STEP). Other fossils are a known limitation: a repeated
name the scan still finds but Inventor no longer references skips the
assembly falsely, and `step-mirror export --force` exports one named file
anyway.

A timed-out export may leave its document open in Inventor without a window.
Each timeout is recorded in `pending-close.json`, and `close_leftovers` closes
those documents before the next export when no window shows them and no
other open document uses them.

Every attempt is appended to `export.log` at the mirror root, one
tab-separated line each: time, outcome, seconds, workspace-relative source,
and the mirror-relative STEP or the reason. At 5 MB the log is renamed to
`export.log.1` (one kept) and a new one is started.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Callable

from pihti_dedup import inventor_session
from pihti_dedup.inventor_session import ExportResult, Session, path_key
from pihti_dedup.inventory import DEFAULT_SKIP_DIRS, VENDOR_PREFIXES

log = logging.getLogger(__name__)

ENV_VAR = "PIHTI_DEDUP_STEP_MIRROR"
FOLDER_SUFFIX = "-step"
STEP_SUFFIX = ".step"
INDEX_NAME = "mirror-index.json"
README_NAME = "README.md"
INDEX_VERSION = 1
SOURCE_EXTENSIONS = frozenset({".ipt", ".iam"})
#: How far a recorded source modification time may drift and still match.
MTIME_TOLERANCE_NS = 2_000_000_000
#: Export attempts kept in the index for the status page.
RECENT_LIMIT = 20

CURRENT = "current"
STALE = "stale"
MISSING = "missing"

#: The outcome of an assembly that would make Inventor ask; see `blocking_reference`.
NEEDS_DOCTOR = "needs-doctor"
#: Names that can make Inventor ask when an assembly opens.
CHECKED_EXTENSIONS = frozenset({".ipt", ".iam", ".ipn"})
LOG_NAME = "export.log"
#: Documents a timed-out export may have left open in Inventor without a window.
PENDING_CLOSE_NAME = "pending-close.json"
CLOSED_LEFTOVER = "closed-leftover"
LOG_ROTATE_BYTES = 5 * 1024 * 1024
#: How much of the log's end is read for the status page.
LOG_TAIL_BYTES = 64 * 1024

NO_CURRENT_STEP = "no current STEP in the mirror"
NOT_MIRRORED = "failed: only parts and assemblies in the default scan scope are mirrored"

#: The background job: seconds to wait on Inventor per export, and after a
#: timeout or failure before the next attempt.
BACKGROUND_BUDGET_SECONDS = 10.0
BACKOFF_SECONDS = 60.0
#: Rest between two background exports. Every export opens a document in the
#: owner's Inventor for a few seconds; one export a minute keeps that
#: unnoticeable while he designs. `step-mirror sync` is the fast fill.
SPACING_SECONDS = 60.0

README_TEXT = """\
# STEP mirror

A STEP copy of every Inventor part (`.ipt`) and assembly (`.iam`) in the
workspace this folder is named after, exported by Inventor itself through
`pihti-dedup`. The folder tree matches the workspace; each file is named after
its source with `.step` appended (`Body.ipt` becomes `Body.ipt.step`).

This folder is regenerable and is not curated source. It sits outside the
workspace and outside git on purpose, and Dropbox carries it to every machine.
Delete any file, or the whole folder, and `pihti-dedup step-mirror sync .` (or
the viewer, while Inventor is open) exports it again. `mirror-index.json`
records which state of each source a STEP was exported from.
"""


def renamed_names(entries) -> frozenset[str]:
    """The rename ledger's old names still open, casefolded.

    A rename the owner marked settled on the Renames page no longer makes
    any assembly ask; its old name may survive only as a fossil string.
    """

    return frozenset(entry.old_name.casefold() for entry in entries if not entry.settled)


def step_mirror_root(workspace: Path | str, environ: Mapping[str, str] | None = None) -> Path:
    """The mirror folder: the override variable, else `<workspace>-step` beside it."""

    env = os.environ if environ is None else environ
    override = env.get(ENV_VAR, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    resolved = Path(workspace).resolve()
    return resolved.parent / f"{resolved.name}{FOLDER_SUFFIX}"


def is_mirrored(path: str | Path) -> bool:
    """True for the extensions the mirror holds a STEP for."""

    return Path(str(path)).suffix.casefold() in SOURCE_EXTENSIONS


def in_scope(relative: str) -> bool:
    """True for an `.ipt` or `.iam` the default scan covers.

    Not under `OldVersions/`, a Pack-and-Go vendor tree, `staging/`, or any
    other directory the scan skips, and not a `.newVer` save leftover.
    """

    if not is_mirrored(relative) or ".newver." in relative.rsplit("/", 1)[-1].casefold():
        return False  # an interrupted Inventor save's leftover is not a document
    folders =[part.casefold() for part in relative.replace("\\", "/").split("/")[:-1]]
    if any(part in DEFAULT_SKIP_DIRS or part == "oldversions" for part in folders):
        return False
    return tuple(folders[:2]) not in VENDOR_PREFIXES


def step_relative(relative: str) -> str:
    """The mirror-relative STEP path for a workspace-relative source path."""

    return f"{relative}{STEP_SUFFIX}"


def _matches(entry: Mapping, mtime_ns: int, size: int) -> bool:
    try:
        recorded_mtime = int(entry["source_mtime_ns"])
        recorded_size = int(entry["source_size"])
    except (KeyError, TypeError, ValueError):
        return False
    return recorded_size == size and abs(recorded_mtime - mtime_ns) < MTIME_TOLERANCE_NS


def _times(count: int) -> str:
    return "twice" if count == 2 else f"{count} times"


def first_blocking(
    names: Iterable[str],
    locations: Mapping[str, Sequence[str]],
    settled: Iterable[str] = (),
    renamed: Iterable[str] | None = None,
) -> tuple[str, str] | None:
    """The first name that would make Inventor ask, and why; None when none would.

    `names` are the filenames the where-used scan lists for one assembly,
    `locations` maps a casefolded filename to every workspace path carrying
    it (`whereused.filename_locations`), and `settled` holds the names the
    rename ledger records as repaired or indirect for that assembly. Only
    part, assembly, and presentation names count; names are taken in
    case-insensitive order so the answer is stable.

    `renamed`, when given, limits "missing" to those names (the rename
    ledger's old names): the byte scan also finds names no reference uses
    any more, such as the template an assembly was started from
    (`Standard (mm).iam`) or the source name of an imported STEP, and on the
    PIHTI workspace those alone would stop every assembly. A repeated name is
    always reported.
    """

    skipped = {name.casefold() for name in settled}
    known = None if renamed is None else {name.casefold() for name in renamed}
    for name in sorted(set(names), key=lambda value: (value.casefold(), value)):
        key = name.casefold()
        if Path(name).suffix.casefold() not in CHECKED_EXTENSIONS or key in skipped:
            continue
        count = len(locations.get(key, ()))
        if count == 0 and (known is None or key in known):
            return name, f"{name} is missing"
        if count > 1:
            return name, f"{name} exists {_times(count)}"
    return None


def blocking_reference(
    names: Iterable[str],
    locations: Mapping[str, Sequence[str]],
    settled: Iterable[str] = (),
    renamed: Iterable[str] | None = None,
) -> str | None:
    """Why opening an assembly with these embedded names would stop Inventor, or None.

    A name with no file in the workspace raises Resolve Link; a name carried
    by two or more files raises Non-Unique Project File Names. The reason
    names the first such file: "board.ipt exists twice",
    "Wide Din Clip.ipt is missing". See `first_blocking` for the arguments.
    """

    found = first_blocking(names, locations, settled, renamed)
    return found[1] if found is not None else None


@dataclass(frozen=True)
class DoctorItem:
    """A stale or missing assembly the mirror will not open until Doctor settles a name."""

    item: MirrorItem
    name: str
    reason: str

    @property
    def path(self) -> str:
        return self.item.path


@dataclass(frozen=True)
class MirrorItem:
    """One Inventor document and the state of its STEP copy."""

    path: str
    step: str
    source_mtime_ns: int
    source_size: int
    state: str
    step_mtime_ns: int | None = None

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def folder(self) -> str:
        return self.path.rsplit("/", 1)[0] if "/" in self.path else "."


@dataclass(frozen=True)
class MirrorStatus:
    """Every mirrored document, by state."""

    root: Path
    items: tuple[MirrorItem, ...]

    def _in(self, state: str) -> tuple[MirrorItem, ...]:
        chosen = [item for item in self.items if item.state == state]
        chosen.sort(key=lambda item: (item.source_mtime_ns, item.path.casefold()))
        return tuple(chosen)

    @cached_property
    def current(self) -> tuple[MirrorItem, ...]:
        return self._in(CURRENT)

    @cached_property
    def stale(self) -> tuple[MirrorItem, ...]:
        """Oldest source first."""

        return self._in(STALE)

    @cached_property
    def missing(self) -> tuple[MirrorItem, ...]:
        """Oldest source first."""

        return self._in(MISSING)

    @cached_property
    def queue(self) -> tuple[MirrorItem, ...]:
        """Every stale or missing document, oldest source first: the export order."""

        waiting = [item for item in self.items if item.state != CURRENT]
        waiting.sort(key=lambda item: (item.source_mtime_ns, item.path.casefold()))
        return tuple(waiting)

    @property
    def total(self) -> int:
        return len(self.items)

    @cached_property
    def _by_path(self) -> dict[str, MirrorItem]:
        return {item.path.casefold(): item for item in self.items}

    def item(self, relative: str) -> MirrorItem | None:
        return self._by_path.get(relative.casefold())


def _replace_with_retry(temporary: Path, target: Path, *, attempts: int = 8, wait: float = 0.25) -> None:
    """`Path.replace` that rides out a sync client's brief lock on the target.

    Dropbox opens a file it just noticed for a moment; a replace in that
    moment raises a permission error on Windows. The index is small and
    rewritten often, so waiting a few hundred milliseconds and trying again
    is the whole cure; the last attempt raises so the caller still logs it.
    """

    for attempt in range(attempts):
        try:
            temporary.replace(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(wait)


class StepMirror:
    """The mirror of one workspace: where each STEP goes, which are current, exports."""

    def __init__(
        self,
        workspace: Path | str,
        root: Path | str | None = None,
        *,
        where_used: Callable[[], object | None] | None = None,
        locations: Callable[[], Mapping[str, Sequence[str]] | None] | None = None,
        settled: Callable[[], Iterable[tuple[str, str]]] | None = None,
        renamed: Callable[[], Iterable[str]] | None = None,
    ) -> None:
        """`where_used`, `locations`, `settled`, and `renamed` feed the pre-check.

        `where_used` returns a `whereused.WhereUsed`, `locations` the
        `filename_locations` map, `settled` the rename ledger's
        `(referrer, old name)` pairs, and `renamed` the ledger's old names
        (`renamed_names`), which limit "missing" to names a recorded rename
        left behind; without it every missing name counts. Without the first
        two no assembly is checked, and every export opens its document as
        before.
        """

        self.workspace = Path(workspace).resolve()
        self.root = Path(root) if root is not None else step_mirror_root(self.workspace)
        self.where_used = where_used
        self.locations = locations
        self.settled = settled
        self.renamed = renamed
        self._lock = threading.RLock()
        self._index_stamp: tuple[int, int] | None = None
        self._index: dict = {}
        self._generation = 0
        self._memo: tuple[object, object, MirrorStatus] | None = None
        self._names_memo: tuple[object, dict[str, tuple[str, ...]]] | None = None

    # ---- the index ----------------------------------------------------------

    @property
    def index_path(self) -> Path:
        return self.root / INDEX_NAME

    def _stamp(self) -> tuple[int, int] | None:
        try:
            stat = self.index_path.stat()
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    @staticmethod
    def _empty() -> dict:
        return {"version": INDEX_VERSION, "entries": {}, "recent": []}

    def _read_index(self) -> dict:
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("entries"), dict):
            return self._empty()
        if not isinstance(payload.get("recent"), list):
            payload["recent"] = []
        return payload

    def index(self) -> dict:
        """The index as last written, re-read only when the file changed."""

        with self._lock:
            stamp = self._stamp()
            if stamp is None:
                self._index_stamp, self._index = None, self._empty()
            elif stamp != self._index_stamp:
                self._index, self._index_stamp = self._read_index(), stamp
            return self._index

    def _write_index(self, index: dict) -> None:
        temporary = self.index_path.with_name(f"{INDEX_NAME}.{os.getpid():x}.tmp")
        try:
            temporary.write_text(
                json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _replace_with_retry(temporary, self.index_path)
        except OSError:
            log.warning("could not write the STEP mirror index at %s", self.index_path, exc_info=True)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def recent(self) -> list[dict]:
        """The last recorded export attempts, newest first.

        Read from the end of `export.log`; a mirror written before the log
        existed falls back to the index's own short `recent` list. Each line is
        a dict with `at`, `path`, `outcome` (as `ExportResult` reports it),
        `kind` (the outcome without its reason), `seconds`, and `detail` (the
        STEP or the reason).
        """

        lines = self._log_tail()
        if lines is not None:
            return lines
        recent = []
        for line in reversed(self.index().get("recent", [])[-RECENT_LIMIT:]):
            outcome = str(line.get("outcome", ""))
            kind, _, detail = outcome.partition(": ")
            recent.append({**line, "outcome": outcome, "kind": kind, "detail": detail})
        return recent

    # ---- the export log -----------------------------------------------------

    @property
    def log_path(self) -> Path:
        return self.root / LOG_NAME

    def log_attempt(self, relative: str, outcome: str, seconds: float = 0.0, reason: str = "") -> None:
        """Append one attempt to `export.log`, rotating it at `LOG_ROTATE_BYTES`.

        Written only into an existing mirror folder; never raises.
        """

        kind, _, detail = outcome.partition(": ")
        if kind == inventor_session.EXPORTED:
            detail = step_relative(relative)
        elif kind == inventor_session.SKIPPED_OPEN:
            detail = detail or "open in Inventor"
        elif kind == inventor_session.TIMED_OUT:
            detail = detail or "Inventor did not answer in time"
        detail = reason or detail
        when = datetime.now().astimezone().isoformat(timespec="seconds")
        fields = (when, kind, f"{seconds:.2f}", relative, detail)
        line = "\t".join(" ".join(str(field).split()) for field in fields) + "\n"
        path = self.log_path
        with self._lock:
            try:
                if not self.root.is_dir():
                    return
                try:
                    if path.stat().st_size >= LOG_ROTATE_BYTES:
                        os.replace(path, path.with_name(f"{LOG_NAME}.1"))
                except FileNotFoundError:
                    pass
                with path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(line)
            except OSError:
                log.warning("could not append to the STEP mirror log at %s", path, exc_info=True)

    def _log_tail(self) -> list[dict] | None:
        try:
            with self.log_path.open("rb") as handle:
                size = handle.seek(0, os.SEEK_END)
                handle.seek(max(0, size - LOG_TAIL_BYTES))
                data = handle.read()
        except OSError:
            return None
        lines = data.decode("utf-8", "replace").splitlines()
        if len(data) >= LOG_TAIL_BYTES and lines:
            lines = lines[1:]  # the first line was cut by the seek
        recent: list[dict] = []
        for text in reversed(lines):
            fields = text.split("\t")
            if len(fields) != 5:
                continue
            when, kind, seconds, path, detail = fields
            try:
                spent = float(seconds)
            except ValueError:
                spent = 0.0
            outcome = f"{kind}: {detail}" if kind == "failed" else kind
            recent.append(
                {
                    "at": when,
                    "path": path,
                    "outcome": outcome,
                    "kind": kind,
                    "seconds": spent,
                    "detail": detail,
                }
            )
            if len(recent) >= RECENT_LIMIT:
                break
        return recent

    # ---- leftovers from a timeout -------------------------------------------

    @property
    def pending_close_path(self) -> Path:
        return self.root / PENDING_CLOSE_NAME

    def pending_close(self) -> list[str]:
        """Workspace-relative documents a timed-out export may have left open."""

        try:
            payload = json.loads(self.pending_close_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        paths = payload.get("paths") if isinstance(payload, dict) else None
        if not isinstance(paths, list):
            return []
        return [path for path in paths if isinstance(path, str)]

    def _write_pending_close(self, paths: list[str]) -> None:
        path = self.pending_close_path
        try:
            if not paths:
                path.unlink(missing_ok=True)
                return
            temporary = path.with_name(f"{PENDING_CLOSE_NAME}.{os.getpid():x}.tmp")
            temporary.write_text(
                json.dumps({"version": 1, "paths": paths}, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
            )
            _replace_with_retry(temporary, path)
        except OSError:
            log.warning("could not write %s", path, exc_info=True)

    def _remember_leftover(self, relative: str) -> None:
        with self._lock:
            pending = self.pending_close()
            if relative.casefold() not in {path.casefold() for path in pending}:
                self._write_pending_close([*pending, relative])

    def close_leftovers(self, session: Session) -> list[str]:
        """Close what earlier timed-out exports left open without a window; never raises.

        Only documents recorded in `pending-close.json` are considered, so
        nothing the mirror did not open is ever closed. A record is forgotten
        after its document closed, or when Inventor no longer holds it; a
        document with a window, one another open document references, or one
        whose close failed stays recorded for the next attempt. Returns the
        closed documents, each also logged as `closed-leftover`.
        """

        with self._lock:
            pending = self.pending_close()
            if not pending:
                return []
            try:
                outcomes = inventor_session.close_leftovers(
                    session, [self.workspace / relative for relative in pending]
                )
            except Exception:  # noqa: BLE001 - a silent Inventor: try again next time
                log.info("step mirror: could not close leftovers; Inventor did not answer")
                return []
            closed: list[str] = []
            keep: list[str] = []
            for relative in pending:
                outcome = outcomes.get(
                    path_key(self.workspace / relative), inventor_session.NOT_OPEN
                )
                if outcome == inventor_session.CLOSED:
                    closed.append(relative)
                    self.log_attempt(
                        relative, CLOSED_LEFTOVER, reason="left open without a window by a timeout"
                    )
                elif outcome != inventor_session.NOT_OPEN:
                    keep.append(relative)
            if keep != pending:
                self._write_pending_close(keep)
            return closed

    # ---- the assembly pre-check ---------------------------------------------

    def _names_by_document(self, index) -> dict[str, tuple[str, ...]]:
        memo = self._names_memo
        if memo is not None and memo[0] is index:
            return memo[1]
        names = {
            path.casefold(): tuple(found)
            for path, found in getattr(index, "document_names", {}).items()
        }
        self._names_memo = (index, names)
        return names

    def reference_context(self):
        """(names by document, locations, settled names by document, renamed), or None."""

        if self.where_used is None or self.locations is None:
            return None
        index = self.where_used()
        locations = self.locations()
        if index is None or locations is None:
            return None
        settled: dict[str, set[str]] = {}
        if self.settled is not None:
            for referrer, name in self.settled():
                key = str(referrer).replace("\\", "/").strip("/").casefold()
                settled.setdefault(key, set()).add(str(name))
        renamed = None if self.renamed is None else frozenset(
            str(name).casefold() for name in self.renamed()
        )
        return self._names_by_document(index), locations, settled, renamed

    def blocker(self, relative: str, context=None) -> tuple[str, str] | None:
        """(name, reason) when opening this assembly would make Inventor ask.

        None for a part, when the pre-check has no where-used data, or when
        every embedded name resolves to exactly one workspace file.
        """

        if Path(relative).suffix.casefold() != ".iam":
            return None
        if context is None:
            context = self.reference_context()
            if context is None:
                return None
        names, locations, settled, renamed = context
        key = relative.casefold()
        return first_blocking(names.get(key, ()), locations, settled.get(key, ()), renamed)

    def needs_doctor(self, status: MirrorStatus) -> tuple[DoctorItem, ...]:
        """The stale or missing assemblies the pre-check would not open, oldest first."""

        context = self.reference_context()
        if context is None:
            return ()
        found = []
        for item in status.queue:
            blocked = self.blocker(item.path, context)
            if blocked is not None:
                found.append(DoctorItem(item=item, name=blocked[0], reason=blocked[1]))
        return tuple(found)

    # ---- where and whether --------------------------------------------------

    def target(self, relative: str) -> Path:
        return self.root / step_relative(relative)

    def _state(
        self, relative: str, mtime_ns: int, size: int, entries: Mapping | None = None
    ) -> tuple[str, int | None]:
        try:
            step_stat = self.target(relative).stat()
        except OSError:
            return MISSING, None
        if entries is None:
            entries = self.index().get("entries", {})
        entry = entries.get(relative.casefold())
        if isinstance(entry, dict):
            current = _matches(entry, mtime_ns, size)
        else:
            current = step_stat.st_mtime_ns >= mtime_ns
        return (CURRENT if current else STALE), step_stat.st_mtime_ns

    def state(
        self, relative: str, mtime_ns: int, size: int, entries: Mapping | None = None
    ) -> MirrorItem:
        """One document's mirror state, without building the whole status."""

        state, step_mtime = self._state(relative, mtime_ns, size, entries)
        return MirrorItem(
            path=relative,
            step=step_relative(relative),
            source_mtime_ns=mtime_ns,
            source_size=size,
            state=state,
            step_mtime_ns=step_mtime,
        )

    def current_step(self, relative: str, mtime_ns: int, size: int) -> Path | None:
        """The STEP to read for this source state, or None when it is not current."""

        item = self.state(relative, mtime_ns, size)
        return self.target(relative) if item.state == CURRENT else None

    def status(self, inventory) -> MirrorStatus:
        """Every mirrored document in `inventory`, memoised per inventory snapshot.

        Rebuilt when the inventory object, the index file, or an export in this
        process changes.
        """

        with self._lock:
            key = (self._stamp(), self._generation)
            memo = self._memo
            if memo is not None and memo[0] is inventory and memo[1] == key:
                return memo[2]
        entries = self.index().get("entries", {})
        items = tuple(
            self.state(record.path, record.mtime_ns, record.size, entries)
            for record in inventory.records
            if in_scope(record.path)
        )
        status = MirrorStatus(root=self.root, items=items)
        with self._lock:
            self._memo = (inventory, key, status)
        return status

    # ---- writing ------------------------------------------------------------

    def ensure_root(self) -> None:
        """Create the mirror folder and its README; only ever called before a write."""

        self.root.mkdir(parents=True, exist_ok=True)
        readme = self.root / README_NAME
        if not readme.exists():
            readme.write_text(README_TEXT, encoding="utf-8")

    def export(
        self,
        session: Session,
        relative: str,
        *,
        timeout: float = inventor_session.DEFAULT_TIMEOUT,
        force: bool = False,
    ) -> ExportResult:
        """Export one workspace document to its mirror STEP and record the attempt.

        An assembly the pre-check blocks is `needs-doctor` and never reaches
        Inventor, unless `force` is set.
        """

        source = self.workspace / relative
        target = self.target(relative)
        if not in_scope(relative):
            return ExportResult(source, target, NOT_MIRRORED)
        try:
            stat = source.stat()
        except OSError:
            return ExportResult(source, target, "failed: no such workspace file")
        blocked = None if force else self.blocker(relative)
        try:
            self.ensure_root()
            if blocked is None:
                target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ExportResult(source, target, f"failed: cannot create the mirror folder ({exc})")
        if blocked is not None:
            result = ExportResult(source, target, NEEDS_DOCTOR, reason=blocked[1])
            self._record(relative, stat, result)
            log.info("step mirror: %s %s (%s)", NEEDS_DOCTOR, relative, blocked[1])
            return result
        result = inventor_session.export_copy(session, source, target, timeout=timeout)
        self._record(relative, stat, result)
        log.info(
            "step mirror: %s %s (%.2f s)", result.outcome, relative, result.seconds
        )
        return result

    def sync(
        self,
        session: Session,
        relatives,
        *,
        budget_seconds: float | None = None,
        per_file_timeout: float = inventor_session.DEFAULT_TIMEOUT,
        on_result: Callable[[ExportResult], None] | None = None,
    ) -> inventor_session.BatchOutcome:
        """Export several documents in order through `export_many`, recording each.

        A file that times out is not tried again within this call: if it
        appears more than once in `relatives` (a caller's queue is not
        expected to repeat one, but this run does not depend on that), the
        second occurrence is reported as the same `timeout` without opening
        Inventor again. `export_many` may still continue past the timeout to
        later files in the same run; see its docstring.
        """

        pairs = [(self.workspace / relative, self.target(relative)) for relative in relatives]
        timed_out_this_run: set[str] = set()

        def export(session: Session, source: Path, _target: Path, *, timeout: float):
            relative = source.relative_to(self.workspace).as_posix()
            key = relative.casefold()
            if key in timed_out_this_run:
                return ExportResult(source, self.target(relative), inventor_session.TIMED_OUT)
            result = self.export(session, relative, timeout=timeout)
            if result.outcome == inventor_session.TIMED_OUT:
                timed_out_this_run.add(key)
            return result

        return inventor_session.export_many(
            session,
            pairs,
            budget_seconds=budget_seconds,
            per_file_timeout=per_file_timeout,
            on_result=on_result,
            export=export,
        )

    def _record(self, relative: str, stat: os.stat_result, result: ExportResult) -> None:
        self.log_attempt(relative, result.outcome, result.seconds, result.reason)
        if result.outcome == inventor_session.TIMED_OUT:
            # Inventor may still hold the document, open and without a window.
            self._remember_leftover(relative)
        if result.outcome == inventor_session.SKIPPED_OPEN:
            return  # nothing changed; no churn in a synced folder
        when = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._lock:
            index = self._read_index()
            if result.exported:
                index["entries"][relative.casefold()] = {
                    "path": relative,
                    "step": step_relative(relative),
                    "source_mtime_ns": stat.st_mtime_ns,
                    "source_size": stat.st_size,
                    "exported_at": when,
                    "seconds": round(result.seconds, 2),
                }
            recent = index.setdefault("recent", [])
            recent.append(
                {
                    "at": when,
                    "path": relative,
                    "outcome": result.outcome,
                    "seconds": round(result.seconds, 2),
                }
            )
            del recent[:-RECENT_LIMIT]
            index["version"] = INDEX_VERSION
            self._write_index(index)
            self._index_stamp = None
            self._generation += 1


_mirrors: dict[tuple[str, str], StepMirror] = {}
_mirrors_lock = threading.Lock()


def mirror_for(workspace: Path | str) -> StepMirror:
    """The shared `StepMirror` for a workspace and the current mirror root."""

    resolved = Path(workspace).resolve()
    root = step_mirror_root(resolved)
    key = (str(resolved), str(root))
    with _mirrors_lock:
        mirror = _mirrors.get(key)
        if mirror is None:
            mirror = _mirrors[key] = StepMirror(resolved, root)
        return mirror


def mirror_status(inventory) -> MirrorStatus:
    """Current, stale, and missing STEP copies for an inventory, memoised per snapshot."""

    return mirror_for(inventory.root).status(inventory)


class MirrorJob:
    """The viewer's background exporter, asked by the snapshot `Ticker` every tick.

    Each tick, at most one stale or missing document is exported, oldest source
    first, and only while a session answers (the probe never launches
    Inventor). A document open in Inventor is passed over for the next one.
    Inventor gets `budget_seconds` without progress per export, and the job
    rests `spacing_seconds` after each export so the owner's Inventor is not
    borrowed more than about once a minute. After a
    timeout or a failure the job waits `backoff_seconds`, and that document is
    passed over until its source changes (the command line still tries it).
    An assembly the pre-check blocks costs Inventor nothing: it is recorded
    once as `needs-doctor`, the tick moves on to the next document, and it is
    passed over until its source changes or the where-used and filename data
    no longer give the same reason (a Doctor fix, a settled rename). The
    reason is re-read from those snapshots every tick; the inventory serial
    is not used, because it moves on every validation and would log the same
    skip again each tick.
    The export runs on its own thread, so a slow Inventor never holds up the
    other snapshots.
    """

    def __init__(
        self,
        mirror: StepMirror,
        inventory: Callable[[], object | None],
        session: Callable[[], Session | None],
        *,
        budget_seconds: float = BACKGROUND_BUDGET_SECONDS,
        backoff_seconds: float = BACKOFF_SECONDS,
        spacing_seconds: float = SPACING_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        threaded: bool = True,
    ) -> None:
        self.mirror = mirror
        self.inventory = inventory
        self.session = session
        self.budget_seconds = budget_seconds
        self.backoff_seconds = backoff_seconds
        self.spacing_seconds = spacing_seconds
        self.clock = clock
        self.threaded = threaded
        self._resume_at = 0.0
        self._deferred: dict[str, tuple[int, int, str]] = {}
        self._doctor: dict[str, tuple[int, int, str]] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def __repr__(self) -> str:
        return "MirrorJob()"

    def deferred(self) -> dict[str, str]:
        """Documents passed over after a failure: path -> outcome."""

        with self._lock:
            return {path: reason for path, (_m, _s, reason) in self._deferred.items()}

    def needs_doctor(self) -> dict[str, str]:
        """Assemblies passed over by the pre-check: path -> reason."""

        with self._lock:
            return {path: reason for path, (_m, _s, reason) in self._doctor.items()}

    def refresh_due(self) -> None:
        if not self.threaded:
            self.step()
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run, name="pihti-step-mirror", daemon=True
            )
            self._thread.start()

    def _run(self) -> None:
        try:
            self.step()
        except Exception:
            log.exception("step mirror tick failed")

    def _passed_over(self, item: MirrorItem, context=None) -> bool:
        key = item.path.casefold()
        state = (item.source_mtime_ns, item.source_size)
        with self._lock:
            known = self._deferred.get(key)
            doctor = self._doctor.get(key)
        if known is not None and known[:2] == state:
            return True
        if doctor is None or doctor[:2] != state:
            return False
        blocked = self.mirror.blocker(item.path, context) if context is not None else None
        return blocked is not None and blocked[1] == doctor[2]

    def _back_off(self) -> None:
        self._resume_at = self.clock() + self.backoff_seconds

    def step(self) -> ExportResult | None:
        """One tick: export at most one document. None when nothing was attempted."""

        if self.clock() < self._resume_at:
            return None
        session = self.session()
        if session is None:
            return None
        self.mirror.close_leftovers(session)
        inventory = self.inventory()
        if inventory is None:
            return None
        context = self.mirror.reference_context() if self._doctor else None
        queue = [
            item
            for item in self.mirror.status(inventory).queue
            if not self._passed_over(item, context)
        ]
        if not queue:
            return None
        try:
            open_paths = session.open_documents()
        except Exception:  # noqa: BLE001 - a silent or vanished Inventor
            self._back_off()
            return None
        skipped: ExportResult | None = None
        for item in queue:
            if path_key(self.mirror.workspace / item.path) in open_paths:
                continue
            result = self.mirror.export(session, item.path, timeout=self.budget_seconds)
            if result.outcome == NEEDS_DOCTOR:
                # Inventor was never asked; record it and try the next document.
                with self._lock:
                    self._doctor[item.path.casefold()] = (
                        item.source_mtime_ns,
                        item.source_size,
                        result.reason,
                    )
                skipped = result
                continue
            with self._lock:
                self._doctor.pop(item.path.casefold(), None)
            if not result.exported and result.outcome != inventor_session.SKIPPED_OPEN:
                with self._lock:
                    self._deferred[item.path.casefold()] = (
                        item.source_mtime_ns,
                        item.source_size,
                        result.outcome,
                    )
                self._back_off()
            elif result.exported:
                self._resume_at = self.clock() + self.spacing_seconds
            return result
        return skipped
