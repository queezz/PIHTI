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
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Mapping
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


class StepMirror:
    """The mirror of one workspace: where each STEP goes, which are current, exports."""

    def __init__(self, workspace: Path | str, root: Path | str | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.root = Path(root) if root is not None else step_mirror_root(self.workspace)
        self._lock = threading.RLock()
        self._index_stamp: tuple[int, int] | None = None
        self._index: dict = {}
        self._generation = 0
        self._memo: tuple[object, object, MirrorStatus] | None = None

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
            temporary.replace(self.index_path)
        except OSError:
            log.warning("could not write the STEP mirror index at %s", self.index_path, exc_info=True)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def recent(self) -> list[dict]:
        """The last recorded export attempts, newest first."""

        return list(reversed(self.index().get("recent", [])))[:RECENT_LIMIT]

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
    ) -> ExportResult:
        """Export one workspace document to its mirror STEP and record the attempt."""

        source = self.workspace / relative
        target = self.target(relative)
        if not in_scope(relative):
            return ExportResult(source, target, NOT_MIRRORED)
        try:
            stat = source.stat()
        except OSError:
            return ExportResult(source, target, "failed: no such workspace file")
        try:
            self.ensure_root()
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ExportResult(source, target, f"failed: cannot create the mirror folder ({exc})")
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
    ) -> list[ExportResult]:
        """Export several documents in order through `export_many`, recording each."""

        pairs = [(self.workspace / relative, self.target(relative)) for relative in relatives]

        def export(session: Session, source: Path, _target: Path, *, timeout: float):
            return self.export(session, source.relative_to(self.workspace).as_posix(), timeout=timeout)

        return inventor_session.export_many(
            session,
            pairs,
            budget_seconds=budget_seconds,
            per_file_timeout=per_file_timeout,
            on_result=on_result,
            export=export,
        )

    def _record(self, relative: str, stat: os.stat_result, result: ExportResult) -> None:
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
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def __repr__(self) -> str:
        return "MirrorJob()"

    def deferred(self) -> dict[str, str]:
        """Documents passed over after a failure: path -> outcome."""

        with self._lock:
            return {path: reason for path, (_m, _s, reason) in self._deferred.items()}

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

    def _passed_over(self, item: MirrorItem) -> bool:
        with self._lock:
            known = self._deferred.get(item.path.casefold())
        return known is not None and known[:2] == (item.source_mtime_ns, item.source_size)

    def _back_off(self) -> None:
        self._resume_at = self.clock() + self.backoff_seconds

    def step(self) -> ExportResult | None:
        """One tick: export at most one document. None when nothing was attempted."""

        if self.clock() < self._resume_at:
            return None
        session = self.session()
        if session is None:
            return None
        inventory = self.inventory()
        if inventory is None:
            return None
        queue = [item for item in self.mirror.status(inventory).queue if not self._passed_over(item)]
        if not queue:
            return None
        try:
            open_paths = session.open_documents()
        except Exception:  # noqa: BLE001 - a silent or vanished Inventor
            self._back_off()
            return None
        for item in queue:
            if path_key(self.mirror.workspace / item.path) in open_paths:
                continue
            result = self.mirror.export(session, item.path, timeout=self.budget_seconds)
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
        return None
