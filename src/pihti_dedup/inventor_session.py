"""Repair assembly references after a rename, through a running Inventor.

A rename on disk leaves every referring assembly naming the old file. Inventor
itself can repoint those references without its resolve dialog, and the order
that works is fixed:

1. open every referring document invisibly while the old filename still
   resolves;
2. rename the file on disk;
3. on each open document, call `ReplaceReference(new_full_path)` on every
   referenced-file descriptor whose *basename* is the old filename (never a
   full-path match: the stored path is whatever Inventor last resolved). When
   other files still carry the old name, a descriptor that resolved to one of
   them in step 1 is left alone: that assembly uses the other copy;
4. `Save2(False)`, the non-interactive save (plain `Save()` can raise a modal
   dialog and block);
5. `Close(True)`, which closes without saving again;
6. reopen, confirm the descriptor names the new file and is not missing, close.

A document already open in the owner's session is never opened, saved, or
closed here: that referrer is skipped with "close it in Inventor first".

Inventor answers no COM call while any modal dialog is on screen, so every call
sequence runs on its own worker thread (with its own COM apartment) and the
caller waits only as long as the worker keeps making progress. When it stops,
the caller gets "Inventor did not answer (a dialog may be open)" instead of a
hung request, and the worker is told to stop at its next step: once cancelled
it renames nothing and saves nothing more, and it closes whatever it opened
when Inventor answers again.

`connect()` is the only function that reaches a real Inventor. Everything else
takes a `Session`, which wraps a callable returning an object with Inventor's
automation surface; tests hand it a fake one.
"""

from __future__ import annotations

import contextlib
import gc
import ntpath
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ContextManager, Iterable, Iterator

REPAIRED = "repaired"
SKIPPED_OPEN = "skipped-open-in-inventor"
NO_DESCRIPTOR = "no-descriptor"
NO_ANSWER = "Inventor did not answer (a dialog may be open)"
CLOSE_FIRST = "open in Inventor: close it first"

#: Seconds without progress before a call sequence is given up on.
DEFAULT_TIMEOUT = 60.0
#: A probe (version, open documents) is one or two calls; it should be quick.
PROBE_TIMEOUT = 5.0

_RENAMED = "\0renamed"


class SessionTimeout(RuntimeError):
    """Inventor stopped answering; `records` is what was settled before that."""

    def __init__(self, message: str = NO_ANSWER, records: dict | None = None) -> None:
        super().__init__(message)
        self.records = dict(records or {})


class RepairRefused(RuntimeError):
    """The repair cannot start safely; nothing was opened for writing or renamed."""


class _Cancelled(BaseException):
    """Raised inside the worker once the caller has given up on it.

    A `BaseException`, so the per-document `except Exception` handlers cannot
    swallow it and carry on saving after the caller reported a failure.
    """


def path_key(path: str | Path) -> str:
    """One comparable form for a Windows path: normalised and casefolded."""

    return ntpath.normpath(str(path)).casefold()


def _name_key(full_name: str) -> str:
    return ntpath.basename(str(full_name)).casefold()


def _reason(exc: BaseException) -> str:
    text = " ".join(str(exc).split()) or type(exc).__name__
    return text if len(text) <= 200 else text[:197] + "..."


def _detached(exc: BaseException) -> BaseException:
    """Drop the traceback, so no frame keeps a COM object alive past its apartment."""

    exc.__traceback__ = None
    exc.__context__ = None
    exc.__cause__ = None
    return exc


class _Run:
    """Shared state between one worker and the caller waiting on it."""

    def __init__(self) -> None:
        self.cond = threading.Condition()
        self.progress = 0
        self.done = False
        self.cancelled = False
        self.result: Any = None
        self.error: BaseException | None = None
        self.records: dict[str, Any] = {}

    def _bump(self) -> None:
        self.progress += 1
        self.cond.notify_all()

    def tick(self) -> None:
        """Report progress; stop here if the caller has given up."""

        with self.cond:
            if self.cancelled:
                raise _Cancelled()
            self._bump()

    def touch(self) -> None:
        """Report progress without ever raising: for cleanup paths."""

        with self.cond:
            self._bump()

    def record(self, key: str, value: Any) -> None:
        with self.cond:
            if self.cancelled:
                raise _Cancelled()
            self.records[key] = value
            self._bump()

    def guarded(self, action: Callable[[], Any], key: str) -> None:
        """Run `action` only if not cancelled, and record that it ran, atomically."""

        with self.cond:
            if self.cancelled:
                raise _Cancelled()
            action()
            self.records[key] = True
            self._bump()


class Session:
    """A running Inventor, reached through `attach()` on a worker thread per call.

    `attach` returns an object with Inventor's automation surface
    (`Documents`, `SoftwareVersion`, ...). It is called on the worker thread,
    inside `apartment()`, because a COM proxy belongs to the apartment that
    created it.
    """

    def __init__(
        self,
        attach: Callable[[], Any],
        *,
        version: str = "",
        apartment: Callable[[], ContextManager] | None = None,
    ) -> None:
        self._attach = attach
        self._apartment = apartment or contextlib.nullcontext
        self._busy = threading.Lock()
        self.version = version

    def run(self, work: Callable[[Any, _Run], Any], *, timeout: float = DEFAULT_TIMEOUT) -> Any:
        """Run `work(application, run)` on a worker; wait while it makes progress."""

        if not self._busy.acquire(blocking=False):
            # A previous sequence is still waiting on Inventor.
            raise SessionTimeout()
        run = _Run()

        def attached() -> Any:
            application = self._attach()
            return work(application, run)

        def target() -> None:
            value: Any = None
            error: BaseException | None = None
            try:
                with self._apartment():
                    try:
                        value = attached()
                    except BaseException as exc:  # noqa: BLE001 - handed to the caller
                        error = _detached(exc)
                    gc.collect()
            except BaseException as exc:  # noqa: BLE001 - the apartment itself failed
                error = error or _detached(exc)
            finally:
                with run.cond:
                    run.result = value
                    run.error = error
                    run.done = True
                    run.cond.notify_all()
                self._busy.release()

        worker = threading.Thread(target=target, name="inventor-session", daemon=True)
        worker.start()
        with run.cond:
            while not run.done:
                seen = run.progress
                run.cond.wait(timeout)
                if not run.done and run.progress == seen:
                    run.cancelled = True
                    raise SessionTimeout(records=run.records)
            if run.error is not None:
                if isinstance(run.error, _Cancelled):
                    raise SessionTimeout(records=run.records)
                raise run.error
            return run.result

    def open_documents(self, *, timeout: float = PROBE_TIMEOUT) -> set[str]:
        """Every document Inventor holds in memory, as `path_key` strings."""

        return self.run(_open_paths, timeout=timeout)


def _open_paths(application: Any, run: _Run) -> set[str]:
    documents = application.Documents
    count = int(documents.Count)
    paths: set[str] = set()
    for position in range(1, count + 1):
        paths.add(path_key(documents.Item(position).FullFileName))
        run.tick()
    return paths


def _descriptors(document: Any, run: _Run) -> Iterator[Any]:
    collection = document.File.ReferencedFileDescriptors
    count = int(collection.Count)
    for position in range(1, count + 1):
        item = collection.Item(position)
        run.tick()
        yield item


def connect(*, timeout: float = PROBE_TIMEOUT) -> Session | None:
    """Attach to the running Inventor, or return None. Never raises.

    None means any of: not Windows, `comtypes` not installed (the `inventor`
    extra), no Inventor running, or Inventor not answering within `timeout`.
    """

    if sys.platform != "win32":
        return None
    try:
        import comtypes
        import comtypes.automation
        import comtypes.client
        import comtypes.client.dynamic
    except Exception:  # noqa: BLE001 - an absent optional extra is just "no session"
        return None

    def attach() -> Any:
        raw = comtypes.client.GetActiveObject("Inventor.Application")
        return comtypes.client.dynamic.Dispatch(raw.QueryInterface(comtypes.automation.IDispatch))

    @contextlib.contextmanager
    def apartment() -> Iterator[None]:
        comtypes.CoInitialize()
        try:
            yield
        finally:
            gc.collect()
            comtypes.CoUninitialize()

    session = Session(attach, apartment=apartment)
    try:
        session.version = session.run(
            lambda application, run: str(application.SoftwareVersion.DisplayVersion),
            timeout=timeout,
        )
    except BaseException:  # noqa: BLE001 - not running, not registered, not answering
        return None
    return session


@dataclass(frozen=True)
class ReferrerPlan:
    path: Path
    open_in_inventor: bool = False
    matches: int = 0
    error: str = ""
    #: References by the old name that resolve to another file carrying it.
    elsewhere: int = 0

    @property
    def state(self) -> str:
        if self.open_in_inventor:
            return CLOSE_FIRST
        if self.error:
            return f"cannot open: {self.error}"
        if not self.matches and self.elsewhere:
            return "uses another file with the old name"
        if not self.matches:
            return "no reference to the old name"
        return f"will repoint {self.matches} reference{'s' if self.matches != 1 else ''}"


@dataclass(frozen=True)
class RepairPlan:
    version: str
    old_name: str
    referrers: tuple[ReferrerPlan, ...]
    target_open: bool = False

    @property
    def repairable(self) -> tuple[Path, ...]:
        return tuple(
            item.path
            for item in self.referrers
            if not item.open_in_inventor and not item.error and item.matches
        )


def plan_repair(
    session: Session,
    referrers: Iterable[Path],
    old_name: str,
    *,
    target: Path | None = None,
    survivors: Iterable[Path] = (),
    timeout: float = DEFAULT_TIMEOUT,
) -> RepairPlan:
    """Which referrers are open in Inventor and which carry a matching descriptor.

    Opens each closed referrer invisibly and closes it again without saving.
    Nothing is written and nothing is renamed.
    """

    paths = [Path(path) for path in referrers]
    old_key = old_name.casefold()
    survivor_keys = {path_key(path) for path in survivors}

    def work(application: Any, run: _Run) -> tuple[bool, list[ReferrerPlan]]:
        owner_open = _open_paths(application, run)
        rows: list[ReferrerPlan] = []
        for path in paths:
            if path_key(path) in owner_open:
                rows.append(ReferrerPlan(path, open_in_inventor=True))
                continue
            try:
                document = application.Documents.Open(str(path), False)
            except Exception as exc:  # noqa: BLE001 - reported per referrer
                rows.append(ReferrerPlan(path, error=_reason(exc)))
                run.tick()
                continue
            try:
                run.tick()
                matches = elsewhere = 0
                for descriptor in _descriptors(document, run):
                    full_name = descriptor.FullFileName
                    if _name_key(full_name) != old_key:
                        continue
                    if path_key(full_name) in survivor_keys:
                        elsewhere += 1
                    else:
                        matches += 1
                rows.append(ReferrerPlan(path, matches=matches, elsewhere=elsewhere))
            except Exception as exc:  # noqa: BLE001 - reported per referrer
                rows.append(ReferrerPlan(path, error=_reason(exc)))
            finally:
                _close(document)
                run.touch()
        target_open = target is not None and path_key(target) in owner_open
        return target_open, rows

    target_open, rows = session.run(work, timeout=timeout)
    return RepairPlan(
        version=session.version, old_name=old_name, referrers=tuple(rows), target_open=target_open
    )


@dataclass(frozen=True)
class RepairResult:
    version: str
    renamed: bool
    outcomes: tuple[tuple[Path, str], ...]
    timed_out: bool = False

    @property
    def repaired(self) -> tuple[Path, ...]:
        return tuple(path for path, outcome in self.outcomes if outcome == REPAIRED)

    @property
    def complete(self) -> bool:
        """Every referrer whose reference resolved to this file was repaired.

        A `no-descriptor` referrer was never applicable to this rename (its
        matching descriptors all resolved to a surviving copy, or it never
        named this file at all) and does not count against completeness.
        """

        return bool(self.outcomes) and all(
            outcome in (REPAIRED, NO_DESCRIPTOR) for _, outcome in self.outcomes
        )


def _close(document: Any) -> None:
    try:
        document.Close(True)
    except Exception:  # noqa: BLE001 - a close failure must not hide the outcome
        pass


def repair_references(
    session: Session,
    referrers: Iterable[Path],
    old_name: str,
    new_path: Path,
    *,
    rename: Callable[[], None],
    survivors: Iterable[Path] = (),
    timeout: float = DEFAULT_TIMEOUT,
) -> RepairResult:
    """Open the referrers, call `rename`, repoint, save, close, and verify.

    The rename is in place, so the old file is `new_path` with `old_name`.
    Raises `RepairRefused` (nothing renamed) when the file itself is open in
    Inventor, and re-raises whatever `rename` raises (nothing renamed or
    saved). `survivors` are other files that keep the old name; a descriptor
    resolved to one of them before the rename is not repointed. Otherwise every referrer gets one outcome: `repaired`,
    `skipped-open-in-inventor`, `no-descriptor`, or `failed: <reason>`.
    """

    new_path = Path(new_path)
    old_path = new_path.with_name(old_name)
    paths = [Path(path) for path in referrers]
    old_key = old_name.casefold()
    new_key = new_path.name.casefold()
    survivor_keys = {path_key(path) for path in survivors}

    def verify(application: Any, path: Path, run: _Run) -> str:
        try:
            document = application.Documents.Open(str(path), False)
        except Exception as exc:  # noqa: BLE001 - reported per referrer
            return f"failed: could not reopen to verify ({_reason(exc)})"
        try:
            run.tick()
            names = [
                (_name_key(descriptor.FullFileName), bool(descriptor.ReferenceMissing))
                for descriptor in _descriptors(document, run)
            ]
        except Exception as exc:  # noqa: BLE001 - reported per referrer
            return f"failed: could not read references to verify ({_reason(exc)})"
        finally:
            _close(document)
            run.touch()
        if any(name == old_key for name, _ in names):
            return f"failed: still references {old_name} after saving"
        found = [missing for name, missing in names if name == new_key]
        if not found:
            return f"failed: the saved document does not reference {new_path.name}"
        if any(found):
            return f"failed: the reference to {new_path.name} is missing"
        return REPAIRED

    def work(application: Any, run: _Run) -> dict[str, Any]:
        owner_open = _open_paths(application, run)
        if path_key(old_path) in owner_open:
            raise RepairRefused(f"{old_name} is {CLOSE_FIRST}")
        opened: list[Any] = []
        targets: list[tuple[Path, Any, set[int]]] = []
        saved: list[Path] = []
        try:
            for path in paths:
                if path_key(path) in owner_open:
                    run.record(str(path), SKIPPED_OPEN)
                    continue
                try:
                    document = application.Documents.Open(str(path), False)
                except Exception as exc:  # noqa: BLE001 - reported per referrer
                    run.record(str(path), f"failed: could not open ({_reason(exc)})")
                    continue
                opened.append(document)
                run.tick()
                # While the old name still resolves: which descriptors point at
                # another file that keeps the name. Those stay as they are.
                elsewhere: set[int] = set()
                if survivor_keys:
                    try:
                        for position, descriptor in enumerate(_descriptors(document, run)):
                            full_name = descriptor.FullFileName
                            if (
                                _name_key(full_name) == old_key
                                and path_key(full_name) in survivor_keys
                            ):
                                elsewhere.add(position)
                    except Exception as exc:  # noqa: BLE001 - reported per referrer
                        run.record(str(path), f"failed: could not read references ({_reason(exc)})")
                        continue
                targets.append((path, document, elsewhere))
            run.guarded(rename, _RENAMED)
            for path, document, elsewhere in targets:
                try:
                    matches = [
                        descriptor
                        for position, descriptor in enumerate(_descriptors(document, run))
                        if position not in elsewhere
                        and _name_key(descriptor.FullFileName) == old_key
                    ]
                    if not matches:
                        run.record(str(path), NO_DESCRIPTOR)
                        continue
                    for descriptor in matches:
                        descriptor.ReplaceReference(str(new_path))
                        run.tick()
                    matches.clear()
                    run.tick()  # the last point to stop before writing
                    document.Save2(False)
                    run.tick()
                    saved.append(path)
                except Exception as exc:  # noqa: BLE001 - reported per referrer
                    run.record(str(path), f"failed: {_reason(exc)}")
        finally:
            for document in reversed(opened):
                _close(document)
                run.touch()
            opened.clear()
            targets.clear()
        for path in saved:
            run.record(str(path), verify(application, path, run))
        return dict(run.records)

    timed_out = False
    try:
        records = session.run(work, timeout=timeout)
    except SessionTimeout as exc:
        records = exc.records
        timed_out = True
    renamed = bool(records.pop(_RENAMED, False))
    missing = f"failed: {NO_ANSWER}" if timed_out else "failed: no outcome was recorded"
    outcomes = tuple((path, str(records.get(str(path), missing))) for path in paths)
    return RepairResult(
        version=session.version, renamed=renamed, outcomes=outcomes, timed_out=timed_out
    )
