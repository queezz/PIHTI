import threading

from pihti_dedup.snapshots import Snapshot, Ticker


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def counting(values: list[int]):
    def build() -> int:
        values.append(len(values) + 1)
        return values[-1]

    return build


def test_first_get_builds_and_second_get_reuses() -> None:
    calls: list[int] = []
    snapshot = Snapshot(counting(calls), interval=5, clock=Clock())

    assert snapshot.peek() is None
    assert snapshot.get() == 1
    assert snapshot.get() == 1
    assert calls == [1]
    assert snapshot.peek() == 1


def test_invalidate_makes_the_next_get_rebuild() -> None:
    calls: list[int] = []
    snapshot = Snapshot(counting(calls), interval=5, clock=Clock())
    snapshot.get()

    snapshot.invalidate()

    assert snapshot.get() == 2
    assert snapshot.get() == 2
    assert calls == [1, 2]


def test_refresh_swaps_the_value() -> None:
    calls: list[int] = []
    snapshot = Snapshot(counting(calls), interval=5, clock=Clock())
    snapshot.get()

    assert snapshot.refresh() is True
    assert snapshot.get() == 2
    assert calls == [1, 2]


def test_refresh_skips_while_a_build_is_running() -> None:
    started = threading.Event()
    release = threading.Event()
    calls: list[int] = []

    def slow() -> int:
        calls.append(1)
        started.set()
        release.wait(1)
        return len(calls)

    snapshot = Snapshot(slow, interval=5, clock=Clock())
    worker = threading.Thread(target=snapshot.get)
    worker.start()
    assert started.wait(1)

    assert snapshot.refresh() is False

    release.set()
    worker.join(1)
    assert calls == [1]


def test_due_follows_interval_idle_interval_and_requests() -> None:
    clock = Clock()
    snapshot = Snapshot(lambda: "value", interval=5, idle_interval=60, clock=clock)

    assert snapshot.due() is False  # nothing built yet: the first get builds

    snapshot.get()  # builds at t=100; a fresh build is not yet "requested since"
    assert snapshot.due(now=104) is False
    assert snapshot.due(now=105) is False
    snapshot.get()
    assert snapshot.due(now=105) is True

    snapshot.refresh()  # at t=100 again; the requested flag resets
    assert snapshot.due(now=105) is False
    assert snapshot.due(now=159) is False
    assert snapshot.due(now=160) is True

    clock.now = 200
    snapshot.refresh_due()
    assert snapshot.due(now=205) is False
    snapshot.get()
    assert snapshot.due(now=205) is True


def test_failed_refresh_keeps_the_old_value() -> None:
    state = {"fail": False}

    def build() -> str:
        if state["fail"]:
            raise RuntimeError("disk vanished")
        return "good"

    snapshot = Snapshot(build, interval=5, clock=Clock())
    assert snapshot.get() == "good"

    state["fail"] = True
    assert snapshot.refresh() is False
    assert snapshot.get() == "good"


def test_invalidate_during_a_build_keeps_the_next_get_honest() -> None:
    calls: list[int] = []
    snapshot = Snapshot(counting(calls), interval=5, clock=Clock())

    def build_then_invalidate() -> int:
        value = len(calls) + 1
        calls.append(value)
        if value == 2:
            snapshot.invalidate()  # a mutation lands while the refresh walks
        return value

    snapshot.build = build_then_invalidate
    snapshot.get()
    snapshot.refresh()

    assert snapshot.get() == 3


def test_ticker_refreshes_due_items_and_survives_errors() -> None:
    class Broken:
        def refresh_due(self) -> None:
            raise RuntimeError("boom")

    clock = Clock()
    calls: list[int] = []
    snapshot = Snapshot(counting(calls), interval=5, clock=clock)
    snapshot.get()
    ticker = Ticker([Broken(), snapshot], period=5)

    ticker.tick()
    assert calls == [1]

    clock.now += 5
    ticker.tick()  # old enough, but nobody asked since it was built
    assert calls == [1]

    snapshot.get()
    ticker.tick()
    assert calls == [1, 2]


def test_ticker_start_is_idempotent_and_stop_joins() -> None:
    ticked = threading.Event()

    class Probe:
        def refresh_due(self) -> None:
            ticked.set()

    ticker = Ticker([Probe()], period=0.01)
    ticker.start()
    ticker.start()

    assert ticked.wait(0.05 * 20)
    ticker.stop()
    assert not ticker.running
