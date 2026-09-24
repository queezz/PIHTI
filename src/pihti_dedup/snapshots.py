"""In-memory snapshots refreshed in the background.

A viewer page should render from what is already known rather than walk the
workspace before every response. A `Snapshot` holds one derived value (the
where-used index, the filename locations, the merge history), builds it
synchronously only when nothing is known yet or after an explicit
`invalidate()`, and is otherwise rebuilt by a `Ticker` thread and swapped in
atomically. A request never waits behind a background rebuild.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Generic, Protocol, Sequence, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class Refreshable(Protocol):
    def refresh_due(self) -> None: ...


def is_due(
    *,
    age: float,
    interval: float,
    idle_interval: float,
    requested: bool,
) -> bool:
    """The shared refresh rule: soon when someone is looking, rarely otherwise."""

    return (requested and age >= interval) or age >= idle_interval


class Snapshot(Generic[T]):
    """One value built on first use, then kept fresh by `refresh()`."""

    def __init__(
        self,
        build: Callable[[], T],
        *,
        interval: float,
        idle_interval: float = 60.0,
        name: str = "",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.build = build
        self.interval = interval
        self.idle_interval = idle_interval
        self.name = name
        self.clock = clock
        self._lock = threading.Lock()  # guards the fields below
        self._build_lock = threading.Lock()  # single-flight for builds
        self._value: T | None = None
        self._has_value = False
        self._built_at = 0.0
        self._invalid = False
        self._generation = 0  # bumped by invalidate(); a build started earlier is stale
        self._requested = False

    def __repr__(self) -> str:
        return f"Snapshot({self.name or self.build!r})"

    def peek(self) -> T | None:
        with self._lock:
            return self._value if self._has_value else None

    def get(self) -> T:
        with self._lock:
            self._requested = True
            if self._has_value and not self._invalid:
                return self._value  # type: ignore[return-value]
        with self._build_lock:
            # A concurrent caller may have built while this one waited.
            with self._lock:
                if self._has_value and not self._invalid:
                    return self._value  # type: ignore[return-value]
                generation = self._generation
            value = self.build()
            self._swap(value, generation)
            return value

    def invalidate(self) -> None:
        with self._lock:
            self._invalid = True
            self._generation += 1

    def refresh(self) -> bool:
        """Rebuild now unless a build is already running; keep the old value on error."""

        if not self._build_lock.acquire(blocking=False):
            return False
        try:
            with self._lock:
                generation = self._generation
            try:
                value = self.build()
            except Exception:
                logger.exception("snapshot refresh failed: %s", self.name or self.build)
                return False
            self._swap(value, generation)
            return True
        finally:
            self._build_lock.release()

    def due(self, now: float | None = None) -> bool:
        with self._lock:
            if not self._has_value:
                return False
            current = self.clock() if now is None else now
            return is_due(
                age=current - self._built_at,
                interval=self.interval,
                idle_interval=self.idle_interval,
                requested=self._requested,
            )

    def refresh_due(self) -> None:
        if self.due():
            self.refresh()

    def _swap(self, value: T, generation: int) -> None:
        with self._lock:
            self._value = value
            self._has_value = True
            self._built_at = self.clock()
            self._requested = False
            # An invalidate() that landed while this build ran describes a
            # change the build may not have seen; keep the next get() honest.
            if generation == self._generation:
                self._invalid = False


class Ticker:
    """A daemon thread that asks each snapshot whether it is due."""

    def __init__(self, snapshots: Sequence[Refreshable], period: float) -> None:
        self.snapshots = tuple(snapshots)
        self.period = period
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(
                target=self._run, name="pihti-snapshot-ticker", daemon=True
            )
            self._thread.start()

    def tick(self) -> None:
        for item in self.snapshots:
            try:
                item.refresh_due()
            except Exception:
                logger.exception("snapshot tick failed: %r", item)

    def _run(self) -> None:
        while not self._stop.wait(self.period):
            self.tick()

    def stop(self, timeout: float = 1.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
