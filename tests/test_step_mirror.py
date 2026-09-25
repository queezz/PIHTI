"""The STEP mirror: where it lives, what is current, the exporter, the
background job, the CLI, and the viewer surfaces.

Every session here is the fake from `inventor_fake`; `conftest.py` keeps
`inventor_session.connect` and `launch` answering None and points the mirror
at a fresh temp folder for every test.
"""

import json
import os
import re
from pathlib import Path

import pytest
from inventor_fake import FakeInventor, fake_session

from pihti_dedup import cli, geometry_preview, inventor_session, step_mirror
from pihti_dedup.inventor_session import EXPORTED, SKIPPED_OPEN, TIMED_OUT
from pihti_dedup.inventory import scan_workspace
from pihti_dedup.step_mirror import (
    CURRENT,
    MISSING,
    NO_CURRENT_STEP,
    STALE,
    MirrorJob,
    StepMirror,
    in_scope,
    step_mirror_root,
)
from pihti_dedup.web import create_app, tile_anchor

SECOND = 1_000_000_000
BASE = 1_700_000_000 * SECOND


def stamp(path: Path, ns: int) -> None:
    os.utime(path, ns=(ns, ns))


def make_workspace(root: Path) -> Path:
    """Three parts and an assembly, oldest first: old.ipt, mid.ipt, frame.iam, new.ipt."""

    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    (root / "PIHTI.ipj").write_bytes(b"")
    files = {
        "Frame/parts/old.ipt": 1,
        "Frame/parts/mid.ipt": 2,
        "Frame/frame.iam": 3,
        "Frame/parts/new.ipt": 4,
    }
    for relative, age in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"geometry {relative}".encode())
        stamp(path, BASE + age * 100 * SECOND)
    return root


def fake_for(root: Path, *, owner_open=()) -> FakeInventor:
    disk = {path: [] for path in root.rglob("*") if path.suffix in {".ipt", ".iam"}}
    return FakeInventor(disk, owner_open=[str(root / item) for item in owner_open])


def inventory_of(root: Path):
    return scan_workspace(root, include_vendor=False, hash_files=False)


# ---- where the mirror lives -------------------------------------------------


def test_the_mirror_is_the_sibling_step_folder_unless_the_variable_names_one(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "PIHTI"
    workspace.mkdir()
    monkeypatch.delenv(step_mirror.ENV_VAR, raising=False)

    assert step_mirror_root(workspace) == tmp_path.resolve() / "PIHTI-step"
    assert step_mirror_root(workspace, environ={}) == tmp_path.resolve() / "PIHTI-step"

    elsewhere = tmp_path / "copies"
    monkeypatch.setenv(step_mirror.ENV_VAR, str(elsewhere))
    assert step_mirror_root(workspace) == elsewhere.resolve()
    assert step_mirror_root(workspace, environ={step_mirror.ENV_VAR: "  "}) == (
        tmp_path.resolve() / "PIHTI-step"
    )
    assert not (tmp_path / "PIHTI-step").exists() and not elsewhere.exists()


def test_only_parts_and_assemblies_in_the_default_scope_are_mirrored() -> None:
    assert in_scope("Frame/parts/Body.ipt") and in_scope("Frame/frame.IAM")
    for path in (
        "Frame/drawing.idw",
        "Frame/export.stl",
        "Frame/OldVersions/Body.ipt",
        "bellows/Design Data/vendor.ipt",
        "Bellows/templates/plate.ipt",
        "staging/import/Body.ipt",
        "Frame/parts/Body.newVer.ipt",
    ):
        assert not in_scope(path), path
    assert StepMirror(Path("/w"), Path("/m")).target("A/lp-box.iam") == Path("/m/A/lp-box.iam.step")
    assert StepMirror(Path("/w"), Path("/m")).target("A/lp-box.ipt") == Path("/m/A/lp-box.ipt.step")


# ---- staleness --------------------------------------------------------------


def test_status_counts_each_state_and_lists_the_oldest_source_first(
    tmp_path: Path, step_mirror_folder: Path
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    mirror = StepMirror(root)
    assert mirror.root == step_mirror_folder

    first = mirror.status(inventory_of(root))
    assert (len(first.current), len(first.stale), len(first.missing)) == (0, 0, 4)
    assert [item.path for item in first.queue] == [
        "Frame/parts/old.ipt",
        "Frame/parts/mid.ipt",
        "Frame/frame.iam",
        "Frame/parts/new.ipt",
    ]
    assert not step_mirror_folder.exists()  # reading never creates the mirror

    # new.ipt: exported by the index, current. old.ipt: the index recorded
    # another state, stale. mid.ipt: no index entry, the STEP is older than
    # the file, stale. frame.iam: no entry, the STEP is newer, current.
    for relative, step_age in (("Frame/parts/mid.ipt", 1), ("Frame/frame.iam", 9)):
        target = mirror.target(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"ISO-10303-21;")
        stamp(target, BASE + step_age * 100 * SECOND)
    for relative in ("Frame/parts/new.ipt", "Frame/parts/old.ipt"):
        mirror.target(relative).write_bytes(b"ISO-10303-21;")
    source = (root / "Frame/parts/new.ipt").stat()
    index = {
        "version": 1,
        "recent": [],
        "entries": {
            "frame/parts/new.ipt": {
                "path": "Frame/parts/new.ipt",
                "source_mtime_ns": source.st_mtime_ns + SECOND,  # within the tolerance
                "source_size": source.st_size,
            },
            "frame/parts/old.ipt": {
                "path": "Frame/parts/old.ipt",
                "source_mtime_ns": BASE,
                "source_size": 3,
            },
        },
    }
    (step_mirror_folder / "mirror-index.json").write_text(json.dumps(index), encoding="utf-8")

    status = mirror.status(inventory_of(root))
    states = {item.path: item.state for item in status.items}
    assert states == {
        "Frame/parts/old.ipt": STALE,
        "Frame/parts/mid.ipt": STALE,
        "Frame/frame.iam": CURRENT,
        "Frame/parts/new.ipt": CURRENT,
    }
    assert [item.path for item in status.stale] == ["Frame/parts/old.ipt", "Frame/parts/mid.ipt"]
    assert status.missing == ()
    assert status.total == 4

    # Memoised per inventory snapshot; a changed index is noticed.
    inventory = inventory_of(root)
    assert mirror.status(inventory) is mirror.status(inventory)
    index["entries"]["frame/parts/old.ipt"]["source_size"] = (root / "Frame/parts/old.ipt").stat().st_size
    index["entries"]["frame/parts/old.ipt"]["source_mtime_ns"] = (
        root / "Frame/parts/old.ipt"
    ).stat().st_mtime_ns
    (step_mirror_folder / "mirror-index.json").write_text(json.dumps(index) + " ", encoding="utf-8")
    assert mirror.status(inventory).item("frame/parts/OLD.ipt").state == CURRENT


# ---- the exporter -----------------------------------------------------------


def test_export_copy_saves_a_copy_through_inventor_and_closes_it(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    target = tmp_path / "out" / "old.ipt.step"
    target.parent.mkdir()

    result = inventor_session.export_copy(fake_session(app), root / "Frame/parts/old.ipt", target)

    assert result.outcome == EXPORTED and result.exported
    assert target.read_bytes().startswith(b"ISO-10303-21;")
    assert not inventor_session.export_temporary(target).exists()
    assert app.log == [
        ("open", "old.ipt", False),
        ("saveas", "old.ipt", "old.ipt.tmp.step", True),
        ("close", "old.ipt", True),
    ]
    assert app.ours() == [] and app.violations == []


def test_export_copy_skips_a_document_open_in_inventor(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root, owner_open=["Frame/parts/old.ipt"])
    target = tmp_path / "old.ipt.step"

    result = inventor_session.export_copy(fake_session(app), root / "Frame/parts/old.ipt", target)

    assert result.outcome == SKIPPED_OPEN
    assert app.log == [] and app.violations == [] and not target.exists()


def test_export_copy_reports_a_failure_and_a_timeout(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    source = root / "Frame/parts/old.ipt"
    app = fake_for(root)
    app.fail_export.add(str(source).casefold())
    target = tmp_path / "old.ipt.step"

    failed = inventor_session.export_copy(fake_session(app), source, target)

    assert failed.outcome == "failed: the translator failed" and not failed.exported
    assert not target.exists() and not inventor_session.export_temporary(target).exists()
    assert app.ours() == []  # closed although the save failed

    stuck = fake_for(root)
    stuck.hang = ("saveas", str(source).casefold())
    try:
        timed_out = inventor_session.export_copy(fake_session(stuck), source, target, timeout=0.2)
    finally:
        stuck.release.set()
    assert timed_out.outcome == TIMED_OUT and not target.exists()


def test_export_many_stops_at_the_budget(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    names = ("old", "mid", "new")
    pairs = [(root / f"Frame/parts/{name}.ipt", tmp_path / f"{name}.ipt.step") for name in names]
    ticks = iter([0.0, 0.0, 4.0, 11.0])

    results = inventor_session.export_many(
        fake_session(fake_for(root)), pairs, budget_seconds=10, clock=lambda: next(ticks)
    )
    assert [result.source.stem for result in results] == ["old", "mid"]
    assert results.stopped_because is None
    empty = inventor_session.export_many(fake_session(fake_for(root)), pairs, budget_seconds=0)
    assert empty == [] and empty.stopped_because is None


def test_export_many_stops_when_a_timeout_leaves_inventor_not_answering(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    names = ("old", "mid", "new")
    pairs = [(root / f"Frame/parts/{name}.ipt", tmp_path / f"{name}.ipt.step") for name in names]

    # The worker that timed out is still stuck on Inventor's own call, so the
    # probe that follows the timeout fails at once too (it needs the same
    # session, which `_busy` still marks as taken).
    stuck = fake_for(root)
    stuck.hang = ("saveas", str(pairs[0][0]).casefold())
    seen: list = []
    try:
        results = inventor_session.export_many(
            fake_session(stuck), pairs, per_file_timeout=0.2, on_result=seen.append
        )
    finally:
        stuck.release.set()
    assert [result.outcome for result in results] == [TIMED_OUT] and seen == results
    assert results.stopped_because == inventor_session.NOT_ANSWERING


def test_export_many_continues_past_a_timeout_when_inventor_still_answers(
    tmp_path: Path, monkeypatch
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    names = ("old", "mid", "new")
    pairs = [(root / f"Frame/parts/{name}.ipt", tmp_path / f"{name}.ipt.step") for name in names]
    session = fake_session(fake_for(root))
    monkeypatch.setattr(session, "open_documents", lambda **_: set())

    attempted: list = []

    def export(session, source, target, *, timeout):
        attempted.append(source.stem)
        outcome = TIMED_OUT if source.stem == "mid" else EXPORTED
        return inventor_session.ExportResult(source, target, outcome)

    results = inventor_session.export_many(session, pairs, export=export)

    assert attempted == ["old", "mid", "new"]
    assert [result.outcome for result in results] == [EXPORTED, TIMED_OUT, EXPORTED]
    assert results.stopped_because is None


def test_export_many_stops_when_the_post_timeout_probe_itself_fails(
    tmp_path: Path, monkeypatch
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    names = ("old", "mid", "new")
    pairs = [(root / f"Frame/parts/{name}.ipt", tmp_path / f"{name}.ipt.step") for name in names]
    session = fake_session(fake_for(root))

    def refuses(**_kwargs):
        raise inventor_session.SessionTimeout()

    monkeypatch.setattr(session, "open_documents", refuses)

    def export(session, source, target, *, timeout):
        outcome = TIMED_OUT if source.stem == "mid" else EXPORTED
        return inventor_session.ExportResult(source, target, outcome)

    results = inventor_session.export_many(session, pairs, export=export)

    assert [result.source.stem for result in results] == ["old", "mid"]
    assert results.stopped_because == inventor_session.NOT_ANSWERING


def test_the_first_export_creates_the_mirror_its_readme_and_the_index(
    tmp_path: Path, step_mirror_folder: Path
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    mirror = StepMirror(root)

    result = mirror.export(fake_session(fake_for(root)), "Frame/frame.iam")

    assert result.exported
    assert (step_mirror_folder / "Frame" / "frame.iam.step").is_file()
    assert "regenerable" in (step_mirror_folder / "README.md").read_text(encoding="utf-8")
    index = json.loads((step_mirror_folder / "mirror-index.json").read_text(encoding="utf-8"))
    entry = index["entries"]["frame/frame.iam"]
    source = (root / "Frame/frame.iam").stat()
    assert (entry["source_mtime_ns"], entry["source_size"]) == (source.st_mtime_ns, source.st_size)
    assert index["recent"][-1]["outcome"] == EXPORTED
    assert str(root).casefold() not in json.dumps(index).casefold()  # no machine path
    assert mirror.state("Frame/frame.iam", source.st_mtime_ns, source.st_size).state == CURRENT
    assert not list(root.rglob("*.step"))  # nothing inside the workspace

    refused = mirror.export(fake_session(fake_for(root)), "Frame/OldVersions/frame.iam")
    assert refused.outcome == step_mirror.NOT_MIRRORED


def test_sync_does_not_retry_a_file_that_already_timed_out_this_run(
    tmp_path: Path, monkeypatch, step_mirror_folder: Path
) -> None:
    """A file that timed out once this run is not opened in Inventor again.

    `export_many` may continue past a timeout to later files (see its own
    tests); this checks the guarantee at the `StepMirror.sync` level, where a
    repeat of the same relative path in the queue must not knock on Inventor's
    door a second time for it.
    """

    root = make_workspace(tmp_path / "PIHTI")
    mirror = StepMirror(root)
    session = fake_session(fake_for(root))
    monkeypatch.setattr(session, "open_documents", lambda **_: set())

    calls: list[str] = []

    def export(session, relative, *, timeout=inventor_session.DEFAULT_TIMEOUT):
        calls.append(relative)
        outcome = TIMED_OUT if relative.casefold() == "frame/parts/mid.ipt" else EXPORTED
        return inventor_session.ExportResult(root / relative, mirror.target(relative), outcome)

    monkeypatch.setattr(mirror, "export", export)

    relatives = [
        "Frame/parts/old.ipt",
        "Frame/parts/mid.ipt",
        "Frame/parts/mid.ipt",  # a repeat in the queue
        "Frame/parts/new.ipt",
    ]
    results = mirror.sync(session, relatives)

    assert [result.outcome for result in results] == [EXPORTED, TIMED_OUT, TIMED_OUT, EXPORTED]
    assert results.stopped_because is None
    assert calls == ["Frame/parts/old.ipt", "Frame/parts/mid.ipt", "Frame/parts/new.ipt"]


# ---- the background job -----------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def job_for(root: Path, app: FakeInventor | None, clock: Clock) -> tuple[MirrorJob, StepMirror]:
    mirror = StepMirror(root)
    session = fake_session(app) if app is not None else None
    job = MirrorJob(
        mirror,
        inventory=lambda: inventory_of(root),
        session=lambda: session,
        clock=clock,
        spacing_seconds=0.0,
        threaded=False,
    )
    return job, mirror


def test_the_job_rests_between_exports_by_default(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    clock = Clock()
    job, _mirror = job_for(root, fake_for(root), clock)
    job.spacing_seconds = 60.0

    assert job.step().exported
    assert job.step() is None, "a second export must wait for the spacing"
    clock.now += 61
    assert job.step().exported


def test_the_job_exports_one_file_per_tick_oldest_first(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    job, mirror = job_for(root, fake_for(root), Clock())

    order = []
    for _ in range(5):
        result = job.step()
        order.append(result.source.name if result else None)
        states = mirror.status(inventory_of(root))
        assert len(states.current) == len([name for name in order if name])

    assert order == ["old.ipt", "mid.ipt", "frame.iam", "new.ipt", None]


def test_the_job_passes_over_files_open_in_inventor(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root, owner_open=["Frame/parts/old.ipt"])
    job, mirror = job_for(root, app, Clock())

    assert job.step().source.name == "mid.ipt"
    assert app.violations == []
    status = mirror.status(inventory_of(root))
    assert status.item("Frame/parts/old.ipt").state == MISSING


def test_the_job_backs_off_after_a_failure_and_passes_that_file_over(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    app.fail_export.add(str(root / "Frame/parts/old.ipt").casefold())
    clock = Clock()
    job, mirror = job_for(root, app, clock)

    failed = job.step()
    assert failed.outcome == "failed: the translator failed"
    clock.now += 59
    assert job.step() is None  # backing off
    clock.now += 2
    assert job.step().source.name == "mid.ipt"  # the failed file waits for a change
    assert job.deferred() == {"frame/parts/old.ipt": "failed: the translator failed"}
    assert mirror.recent()[1]["outcome"] == "failed: the translator failed"

    app.fail_export.clear()
    stamp(root / "Frame/parts/old.ipt", BASE + 999 * SECOND)
    assert job.step().source.name == "frame.iam"
    assert job.step().source.name == "new.ipt"
    assert job.step().source.name == "old.ipt"  # changed since the failure


def test_the_job_backs_off_after_a_timeout(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    app.hang = ("saveas", str(root / "Frame/parts/old.ipt").casefold())
    clock = Clock()
    job, _mirror = job_for(root, app, clock)
    job.budget_seconds = 0.2
    try:
        assert job.step().outcome == TIMED_OUT
        clock.now += 30
        assert job.step() is None
    finally:
        app.release.set()


def test_the_job_does_nothing_without_a_session(tmp_path: Path, step_mirror_folder: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    job, _mirror = job_for(root, None, Clock())

    assert job.step() is None
    job.refresh_due()
    assert not step_mirror_folder.exists()


def test_the_viewer_registers_the_job_with_the_ticker_only_when_refreshing(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")

    assert "pihti_step_mirror_job" not in create_app(root).extensions
    app = create_app(root, refresh_seconds=5)
    job = app.extensions["pihti_step_mirror_job"]
    assert isinstance(job, MirrorJob)
    client = app.test_client()
    client.get("/health")
    assert job in app.extensions["pihti_ticker"].snapshots
    app.extensions["pihti_ticker"].stop()


# ---- the command line -------------------------------------------------------


def test_cli_status_counts_without_creating_anything(
    tmp_path: Path, capsys, step_mirror_folder: Path
) -> None:
    root = make_workspace(tmp_path / "PIHTI")

    assert cli.main(["step-mirror", "status", str(root)]) == 0
    out = capsys.readouterr().out
    assert "Inventor files: 4" in out and "current: 0" in out and "missing: 4" in out
    assert out.index("Frame\\parts\\old.ipt") < out.index("Frame\\parts\\new.ipt")
    assert not step_mirror_folder.exists()


def test_cli_sync_exports_everything_through_the_running_inventor(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root, owner_open=["Frame/frame.iam"])
    monkeypatch.setattr(inventor_session, "connect", lambda **_: fake_session(app))

    code = cli.main(["step-mirror", "sync", str(root)])

    out = capsys.readouterr().out
    assert code == 0
    assert out.count("exported ") >= 3 and "Frame\\frame.iam (open in Inventor)" in out
    assert "exported 3 · not exported 0 · not started 0" in out
    status = StepMirror(root).status(inventory_of(root))
    assert len(status.current) == 3 and [item.path for item in status.missing] == ["Frame/frame.iam"]


def test_cli_sync_stops_at_the_budget(tmp_path: Path, monkeypatch, capsys) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    monkeypatch.setattr(inventor_session, "connect", lambda **_: fake_session(fake_for(root)))

    assert cli.main(["step-mirror", "sync", str(root), "--budget-seconds", "0"]) == 0
    assert "exported 0 · not exported 0 · not started 4" in capsys.readouterr().out


def test_cli_sync_without_inventor_exports_nothing(
    tmp_path: Path, capsys, step_mirror_folder: Path
) -> None:
    root = make_workspace(tmp_path / "PIHTI")

    assert cli.main(["step-mirror", "sync", str(root)]) == 2
    assert "pass --launch" in capsys.readouterr().err
    assert not step_mirror_folder.exists()


def test_cli_sync_launch_starts_a_hidden_inventor_and_always_quits_it(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    quits: list = []
    monkeypatch.setattr(
        inventor_session, "launch", lambda **_: (fake_session(app), lambda: quits.append(1))
    )

    assert cli.main(["step-mirror", "sync", str(root), "--launch"]) == 0
    assert "started hidden" in capsys.readouterr().out
    assert quits == [1]

    # A failure still quits the launched Inventor.
    def broken(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(StepMirror, "sync", broken)
    with pytest.raises(RuntimeError):
        cli.main(["step-mirror", "sync", str(root), "--launch"])
    assert quits == [1, 1]


def test_cli_sync_launch_uses_a_running_inventor_instead(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    monkeypatch.setattr(inventor_session, "connect", lambda **_: fake_session(fake_for(root)))

    def never(**_kwargs):
        raise AssertionError("a running Inventor must not be launched again")

    monkeypatch.setattr(inventor_session, "launch", never)
    assert cli.main(["step-mirror", "sync", str(root), "--launch"]) == 0
    assert "started hidden" not in capsys.readouterr().out


def test_cli_sync_reports_when_inventor_stops_answering_after_a_timeout(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    session = fake_session(fake_for(root))
    monkeypatch.setattr(inventor_session, "connect", lambda **_: session)

    probe_calls = {"n": 0}

    def open_documents(**_kwargs):
        probe_calls["n"] += 1
        if probe_calls["n"] == 1:
            return set()  # the CLI's own open-in-Inventor check, before sync starts
        raise inventor_session.SessionTimeout()  # the post-timeout probe finds no one home

    monkeypatch.setattr(session, "open_documents", open_documents)

    def export(self, session, relative, *, timeout=inventor_session.DEFAULT_TIMEOUT):
        outcome = TIMED_OUT if relative == "Frame/parts/mid.ipt" else EXPORTED
        return inventor_session.ExportResult(self.workspace / relative, self.target(relative), outcome)

    monkeypatch.setattr(step_mirror.StepMirror, "export", export)

    code = cli.main(["step-mirror", "sync", str(root)])

    out = capsys.readouterr().out
    assert code == 1
    assert "exported 1 · not exported 1 · not started 2" in out
    assert f"stopped: {inventor_session.NOT_ANSWERING} · 2 not started" in out


def test_cli_sync_lists_failures_by_path_and_outcome_when_it_runs_to_the_end(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    session = fake_session(fake_for(root))
    monkeypatch.setattr(inventor_session, "connect", lambda **_: session)
    monkeypatch.setattr(session, "open_documents", lambda **_: set())

    def export(self, session, relative, *, timeout=inventor_session.DEFAULT_TIMEOUT):
        if relative == "Frame/parts/mid.ipt":
            outcome = TIMED_OUT
        elif relative == "Frame/parts/new.ipt":
            outcome = "failed: the translator failed"
        else:
            outcome = EXPORTED
        return inventor_session.ExportResult(self.workspace / relative, self.target(relative), outcome)

    monkeypatch.setattr(step_mirror.StepMirror, "export", export)

    code = cli.main(["step-mirror", "sync", str(root)])

    out = capsys.readouterr().out
    assert code == 1
    assert "exported 2 · not exported 2 · not started 0" in out
    assert "stopped:" not in out
    assert "Frame\\parts\\mid.ipt: timeout" in out
    assert "Frame\\parts\\new.ipt: failed: the translator failed" in out


def test_cli_export_one_file(tmp_path: Path, monkeypatch, capsys, step_mirror_folder: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")

    assert cli.main(["step-mirror", "export", str(root), "Frame/frame.iam"]) == 2
    assert "not running" in capsys.readouterr().err

    monkeypatch.setattr(inventor_session, "connect", lambda **_: fake_session(fake_for(root)))
    assert cli.main(["step-mirror", "export", str(root), "Frame\\frame.iam"]) == 0
    assert "exported" in capsys.readouterr().out
    assert (step_mirror_folder / "Frame" / "frame.iam.step").is_file()

    (root / "Frame" / "notes.stl").write_bytes(b"solid")
    assert cli.main(["step-mirror", "export", str(root), "Frame/notes.stl"]) == 2
    assert cli.main(["step-mirror", "export", str(root), "Frame/absent.ipt"]) == 2
    assert cli.main(["step-mirror", "export", str(root), "../outside.ipt"]) == 2


def test_cli_step_mirror_refuses_a_workspace_without_an_ipj(tmp_path: Path, capsys) -> None:
    for command in (["status"], ["sync"], ["export"]):
        args = ["step-mirror", *command, str(tmp_path)]
        if command == ["export"]:
            args.append("Frame/frame.iam")
        assert cli.main(args) == 2
    assert "not an Inventor workspace" in capsys.readouterr().err


# ---- the viewer -------------------------------------------------------------


def export_now(root: Path) -> None:
    StepMirror(root).export(fake_session(fake_for(root)), "Frame/frame.iam")


def test_the_mesh_route_turns_an_inventor_file_from_its_current_mirror_step(
    tmp_path: Path, monkeypatch
) -> None:
    if ".stl" not in geometry_preview.available_extensions():
        pytest.skip("the 'preview' extra is not installed")
    import numpy as np

    root = make_workspace(tmp_path / "PIHTI")
    loaded: list = []

    def load(path):
        loaded.append(Path(path))
        return np.array([[(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 0, 0), (1, 0, 0), (0, 0, 1)]])

    monkeypatch.setattr(geometry_preview, "available_extensions", lambda: frozenset({".stl", ".step"}))
    monkeypatch.setattr(geometry_preview, "load_triangles", load)
    client = create_app(root).test_client()
    url = "/mesh/Frame/frame.iam"

    missing = client.get(url)
    assert missing.status_code == 404 and missing.get_json() == {"reason": NO_CURRENT_STEP}

    export_now(root)
    catalog = client.get("/catalog/Frame").get_data(as_text=True)
    key = re.search(r'data-mesh="/mesh/Frame/frame.iam\?v=([^"]+)"', catalog).group(1)
    assert re.fullmatch(r"[0-9a-f]+-[0-9a-f]+-s[0-9a-f]+-m\d+", key) and "-s0-" not in key

    served = client.get(f"{url}?v={key}")
    assert served.status_code == 200 and served.mimetype == "application/octet-stream"
    assert served.headers["Cache-Control"] == "private, max-age=31536000, immutable"
    assert loaded == [StepMirror(root).target("Frame/frame.iam")]

    # A resave makes the STEP stale: refused, never the old geometry.
    stamp(root / "Frame" / "frame.iam", BASE + 9_999 * SECOND)
    stale = client.get(url)
    assert stale.status_code == 404 and stale.get_json() == {"reason": NO_CURRENT_STEP}


def test_the_inspector_offers_export_now_only_with_a_session(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")

    def inspector_of(html: str) -> str:
        return html.split('<section class="rail-card inspector"', 1)[1].split("</section>", 1)[0]

    without = inspector_of(create_app(root).test_client().get("/catalog/Frame").get_data(as_text=True))
    form = re.search(r"<form[^>]*data-inspector-step-export[^>]*>(.*?)</form>", without, re.S)
    assert form and f'data-reason="{NO_CURRENT_STEP}"' in form.group(0) and " hidden>" in form.group(0)
    assert "3D needs the STEP mirror · Open Inventor to export" in " ".join(form.group(1).split())
    assert "<button" not in form.group(1) and "action=" not in form.group(0)

    app = fake_for(root)
    viewer = create_app(root, session_factory=lambda: fake_session(app))
    html = inspector_of(viewer.test_client().get("/catalog/Frame").get_data(as_text=True))
    assert '3D needs the STEP mirror · <button class="copy-path" type="submit">export now</button>' in html
    assert f'name="token" value="{viewer.config["FORM_TOKEN"]}"' in html

    script = viewer.test_client().get("/static/dedup.js").get_data(as_text=True)
    assert 'stepForm.action = part + "/step-export"' in script
    assert "error.reason === stepForm.dataset.reason" in script


def test_export_now_is_guarded_exports_and_returns_to_the_file(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    viewer = create_app(root, session_factory=lambda: fake_session(app))
    client = viewer.test_client()
    token = viewer.config["FORM_TOKEN"]
    url = "/part/Frame/frame.iam/step-export"

    assert client.post(url, data={"origin": "Frame"}).status_code == 403
    assert client.post(url, data={"token": "wrong"}).status_code == 403
    remote = client.post(url, data={"token": token}, environ_base={"REMOTE_ADDR": "10.0.0.8"})
    assert remote.status_code == 403
    assert not StepMirror(root).root.exists()
    (root / "Frame" / "export.stl").write_bytes(b"solid")
    assert client.post("/part/Frame/export.stl/step-export", data={"token": token}).status_code == 400

    done = client.post(url, data={"token": token, "origin": "Frame"})
    assert done.status_code == 302
    location = done.headers["Location"]
    assert location.startswith("/catalog/Frame?") and "step=exported" in location
    assert location.endswith("#" + tile_anchor("Frame/frame.iam"))
    assert StepMirror(root).target("Frame/frame.iam").is_file()
    page = client.get(location.split("#", 1)[0]).get_data(as_text=True)
    assert "STEP exported: frame.iam" in page

    from_part = client.post(url, data={"token": token, "origin": "part"})
    assert from_part.headers["Location"].startswith("/part/Frame/frame.iam?")


def test_export_now_without_inventor_says_so(tmp_path: Path, step_mirror_folder: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    viewer = create_app(root)
    client = viewer.test_client()

    done = client.post(
        "/part/Frame/frame.iam/step-export",
        data={"token": viewer.config["FORM_TOKEN"], "origin": "part"},
        follow_redirects=True,
    )
    assert "STEP not exported: Inventor is not running" in done.get_data(as_text=True)
    assert not step_mirror_folder.exists()


def test_the_part_page_names_the_step_and_turns_a_current_one(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    client = create_app(root).test_client()

    before = client.get("/part/Frame/frame.iam").get_data(as_text=True)
    assert "<dt>STEP</dt><dd>none</dd>" in before
    assert "Open Inventor to export" in before and "Export STEP now" not in before
    assert "data-mesh-viewer" not in before

    with_session = create_app(root, session_factory=lambda: fake_session(app)).test_client()
    offered = with_session.get("/part/Frame/frame.iam").get_data(as_text=True)
    assert 'action="/part/Frame/frame.iam/step-export"' in offered and "Export STEP now" in offered

    export_now(root)
    after = client.get("/part/Frame/frame.iam").get_data(as_text=True)
    assert re.search(r"<dt>STEP</dt><dd>\d{4}-\d\d-\d\d \d\d:\d\d</dd>", after)
    assert "Export STEP now" not in after and "Open Inventor to export" not in after
    assert re.search(r'data-mesh-viewer data-mesh="/mesh/Frame/frame.iam\?v=[0-9a-f]+-[0-9a-f]+-s[0-9a-f]+-m', after)

    stamp(root / "Frame" / "frame.iam", BASE + 9_999 * SECOND)
    stale = client.get("/part/Frame/frame.iam").get_data(as_text=True)
    assert ", older than the file</dd>" in stale and "data-mesh-viewer" not in stale

    other = client.get("/part/Frame/parts/old.ipt").get_data(as_text=True)
    assert "<dt>STEP</dt>" in other
    (root / "Frame" / "export.stl").write_bytes(b"solid")
    assert "<dt>STEP</dt>" not in client.get("/part/Frame/export.stl").get_data(as_text=True)


def test_the_top_bar_counts_current_copies_and_links_the_mirror_page(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    client = create_app(root).test_client()

    catalog = client.get("/catalog").get_data(as_text=True)
    line = re.search(r'<a class="mirror-status" href="/step-mirror"[^>]*>([^<]*)</a>', catalog)
    assert line and line.group(1) == "STEP mirror 0 / 4"
    assert catalog.index("mirror-status") < catalog.index('class="version"')

    export_now(root)
    assert "STEP mirror 1 / 4</a>" in client.get("/catalog").get_data(as_text=True)
    page = client.get("/step-mirror").get_data(as_text=True)
    assert 'class="mirror-status is-current"' in page


def test_the_mirror_page_lists_what_waits_and_what_was_exported(
    tmp_path: Path, step_mirror_folder: Path
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    client = create_app(root).test_client()

    page = client.get("/step-mirror").get_data(as_text=True)
    assert "<h1>STEP mirror</h1>" in page
    assert "Inventor is not running; nothing is exported." in page
    assert "The folder is created with the first export." in page
    assert str(step_mirror_folder).replace("/", "\\") in page
    missing = page.split('id="sec-missing"', 1)[1].split("</section>", 1)[0]
    assert missing.index("old.ipt") < missing.index("new.ipt")
    assert "<small>Frame\\parts</small>" in missing
    assert "Nothing exported yet." in page
    for anchor in ("#sec-missing", "#sec-stale", "#sec-recent"):
        assert f'href="{anchor}"' in page
    assert not step_mirror_folder.exists()

    export_now(root)
    app = fake_for(root)
    running = create_app(root, session_factory=lambda: fake_session(app)).test_client()
    page = running.get("/step-mirror").get_data(as_text=True)
    assert "Inventor 2027.1 is running." in page
    recent = page.split('id="sec-recent"', 1)[1].split("</section>", 1)[0]
    assert "Frame\\frame.iam" in recent and "<small>exported</small>" in recent
    assert "frame.iam" not in page.split('id="sec-missing"', 1)[1].split("</section>", 1)[0]
    assert "The folder is created" not in page


def test_the_index_write_rides_out_a_brief_lock(tmp_path: Path, monkeypatch) -> None:
    from pihti_dedup import step_mirror as module

    source = tmp_path / "index.tmp"
    source.write_text("{}", encoding="utf-8")
    target = tmp_path / "mirror-index.json"
    calls = {"n": 0}
    original = Path.replace

    def flaky(self, other):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError(5, "Access is denied")
        return original(self, other)

    monkeypatch.setattr(Path, "replace", flaky)
    monkeypatch.setattr(module.time, "sleep", lambda _s: None)
    module._replace_with_retry(source, target)

    assert target.read_text(encoding="utf-8") == "{}"
    assert calls["n"] == 3


def test_the_index_write_gives_up_after_the_last_attempt(tmp_path: Path, monkeypatch) -> None:
    import pytest

    from pihti_dedup import step_mirror as module

    source = tmp_path / "index.tmp"
    source.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(Path, "replace", lambda self, other: (_ for _ in ()).throw(PermissionError(5, "denied")))
    monkeypatch.setattr(module.time, "sleep", lambda _s: None)
    with pytest.raises(PermissionError):
        module._replace_with_retry(source, tmp_path / "mirror-index.json", attempts=3)
