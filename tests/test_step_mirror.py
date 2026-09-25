"""The STEP mirror: where it lives, what is current, the exporter, the
background job, the CLI, and the viewer surfaces.

Every session here is the fake from `inventor_fake`; `conftest.py` keeps
`inventor_session.connect` and `launch` answering None and points the mirror
at a fresh temp folder for every test.
"""

import json
import os
import re
import time
from pathlib import Path

import pytest
from inventor_fake import FakeInventor, fake_session, reference_bytes

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
    blocking_reference,
    in_scope,
    step_mirror_root,
)
from pihti_dedup.web import create_app, tile_anchor
from pihti_dedup.whereused import build_index, filename_locations

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
    # One line per folder, the open file listed by short name with its folder.
    assert re.search(r"^Frame/parts  3 exported  \d+\.\d s$", out, re.M)
    assert "  frame.iam: open in Inventor  (Frame)" in out
    assert "exported 3 · not exported 0 · not started 0 · 0 need Doctor" in out
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
    # The sync runs folder by folder: frame.iam, old.ipt, then mid.ipt times
    # out and the silent probe stops the batch before new.ipt.
    assert "exported 2 · not exported 1 · not started 1" in out
    assert f"stopped: {inventor_session.NOT_ANSWERING} · 1 not started" in out


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
    assert "  mid.ipt: timeout  (Frame/parts)" in out
    assert "  new.ipt: failed: the translator failed  (Frame/parts)" in out


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

    def load(path, *, fine=False):
        loaded.append((Path(path), fine))
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
    assert loaded == [(StepMirror(root).target("Frame/frame.iam"), True)]

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
    assert '<strong aria-current="page">STEP mirror</strong>' in page
    assert 'class="is-current" aria-current="page">STEP mirror</a>' in page
    assert 'class="work-grid two-rail doctor-session"' in page
    assert "Start Inventor, open PIHTI.ipj, then come back" in page
    assert "Created by the first export" in page
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
    assert "Inventor 2027.1" in page
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


# ---- the assembly pre-check -------------------------------------------------


def test_blocking_reference_names_a_missing_or_repeated_file_and_nothing_else() -> None:
    locations = {
        "board.ipt": ("A/board.ipt", "B/board.ipt"),
        "plate.ipt": ("A/plate.ipt",),
        "nut.ipt": ("A/nut.ipt", "B/nut.ipt", "C/nut.ipt"),
        "sub.iam": ("A/sub.iam",),
    }

    assert blocking_reference(["plate.ipt", "sub.iam"], locations) is None
    assert blocking_reference(["plate.ipt", "Wide Din Clip.ipt"], locations) == (
        "Wide Din Clip.ipt is missing"
    )
    assert blocking_reference(["Board.ipt", "plate.ipt"], locations) == "Board.ipt exists twice"
    assert blocking_reference(["nut.ipt"], locations) == "nut.ipt exists 3 times"
    # Drawings and exports never make an assembly ask; only parts,
    # assemblies, and presentations are looked up.
    assert blocking_reference(["gone.idw", "gone.stp", "plate.ipt"], locations) is None
    assert blocking_reference(["gone.ipn"], locations) == "gone.ipn is missing"
    # A name the ledger settled for this assembly is a fossil, not a reference.
    assert blocking_reference(["Wide Din Clip.ipt"], locations, ["wide din clip.IPT"]) is None
    assert blocking_reference(
        ["board.ipt", "Wide Din Clip.ipt"], locations, ["Wide Din Clip.ipt"]
    ) == "board.ipt exists twice"
    # Stable: the first name in case-insensitive order is the one reported.
    assert blocking_reference(["zeta.ipt", "Alpha.ipt"], {}) == "Alpha.ipt is missing"
    # With the ledger's open old names, "missing" is only a name a rename left
    # behind; a template fossil is not. A repeated name always counts.
    open_renames = {"wide din clip.ipt"}
    assert blocking_reference(["Standard (mm).iam", "plate.ipt"], locations, renamed=open_renames) is None
    assert blocking_reference(
        ["Standard (mm).iam", "Wide Din Clip.ipt"], locations, renamed=open_renames
    ) == "Wide Din Clip.ipt is missing"
    assert blocking_reference(["board.ipt"], locations, renamed=()) == "board.ipt exists twice"


def test_a_missing_name_blocks_until_its_rename_is_settled(tmp_path: Path) -> None:
    from pihti_dedup.renames import RenameEntry, append_entry, read_ledger, set_settled

    root = make_workspace(tmp_path / "PIHTI")
    frame = root / "Frame" / "frame.iam"
    frame.write_bytes(
        reference_bytes(
            "C:\\Templates\\Standard (mm).iam", "C:\\old\\Frame\\parts\\Wide Din Clip.ipt"
        )
    )
    mirror = StepMirror(
        root,
        where_used=lambda: build_index(root),
        locations=lambda: filename_locations(root),
        renamed=lambda: step_mirror.renamed_names(read_ledger(root)),
        retired=lambda: step_mirror.retired_names(read_ledger(root)),
    )
    # The template name is exempt; a part no file carries is missing even
    # when no rename is recorded for it.
    assert mirror.blocker("Frame/frame.iam") == ("Wide Din Clip.ipt", "Wide Din Clip.ipt is missing")

    entry = append_entry(
        root,
        RenameEntry(
            id="",
            timestamp="2026-08-06T13:36:40+00:00",
            old_path="Frame/parts/Wide Din Clip.ipt",
            new_path="Frame/parts/Wide Din Clip V1.ipt",
            old_name="Wide Din Clip.ipt",
            new_name="Wide Din Clip V1.ipt",
            where_used=("Frame/frame.iam",),
        ),
    )
    assert mirror.blocker("Frame/frame.iam") == ("Wide Din Clip.ipt", "Wide Din Clip.ipt is missing")

    set_settled(root, entry.id, True)  # the owner repointed it in Inventor
    assert step_mirror.retired_names(read_ledger(root)) == frozenset({"wide din clip.ipt"})
    assert mirror.blocker("Frame/frame.iam") is None


def test_a_plainly_missing_part_blocks_and_names_itself() -> None:
    locations = {"plate.ipt": ("A/plate.ipt",)}

    # No rename is recorded for it: it lived on someone else's disk.
    assert blocking_reference(["plate.ipt", "ICF70FLMG4MBA.ipt"], locations, renamed=()) == (
        "ICF70FLMG4MBA.ipt is missing"
    )
    # URL-encoded and case variants are one name, reported once, decoded.
    problems = step_mirror.reference_problems(
        ["ICF70F%201%E5%80%8B.ipt", "icf70f 1個.IPT", "plate.ipt"], locations
    )
    assert [kind for _name, _reason, kind in problems] == ["missing"]
    assert problems[0][1].casefold() == "icf70f 1個.ipt is missing"
    # A copy only under OldVersions/ is not where Inventor resolves the name.
    assert blocking_reference(
        ["gone.ipt"], {"gone.ipt": ("Frame/OldVersions/gone.ipt",)}
    ) == "gone.ipt is missing"
    # The byte scan cuts a name that crosses a storage sector; the tail of a
    # longer name the same assembly embeds is not a reference of its own.
    assert blocking_reference(["Standard (mm).iam", "rd (mm).iam"], locations) is None
    assert blocking_reference(["Rotary_handle.ipt", "ary_handle.ipt"], {
        "rotary_handle.ipt": ("A/Rotary_handle.ipt",)
    }) is None
    # A whole word is not a fragment: "Clip.ipt" is its own missing part.
    assert blocking_reference(["Wide Din Clip.ipt", "Clip.ipt"], {
        "wide din clip.ipt": ("A/Wide Din Clip.ipt",)
    }) == "Clip.ipt is missing"


def test_template_names_resolve_outside_the_workspace(
    tmp_path: Path, no_machine_inventor_folders: Path
) -> None:
    # Built in, whatever the machine holds.
    for name in ("Standard (mm).iam", "standard (IN).iam", "Standard.ipt", "Sheet Metal (mm).ipt"):
        assert step_mirror.resolves_outside(name)
    assert not step_mirror.resolves_outside("Bracket.ipt")
    # And whatever Inventor's own Templates folder holds, language folders too.
    metric = no_machine_inventor_folders / "Templates" / "en-US" / "Metric"
    metric.mkdir(parents=True)
    (metric / "Lab Frame (mm).iam").write_bytes(b"template")
    step_mirror._template_names.clear()
    assert step_mirror.resolves_outside("lab frame (MM).iam")

    locations = {"plate.ipt": ("A/plate.ipt",)}
    outside = step_mirror.OutsideNames(tmp_path)
    assert blocking_reference(
        ["Lab Frame (mm).iam", "Standard (in).iam", "plate.ipt"], locations, outside=outside
    ) is None
    # The old name of a rename still open is never exempt.
    assert blocking_reference(
        ["Standard (mm).iam"], locations, renamed={"standard (mm).iam"}, outside=outside
    ) == "Standard (mm).iam is missing"


def test_content_center_parts_resolve_outside_the_workspace(
    tmp_path: Path, no_machine_inventor_folders: Path
) -> None:
    library = no_machine_inventor_folders / "Content Center Files" / "R2027" / "en-US"
    family = library / "ISO 4762"
    family.mkdir(parents=True)
    (family / "ISO 4762 M4 x 12.ipt").write_bytes(b"screw")
    (family / "OldVersions").mkdir()
    (family / "OldVersions" / "ISO 4762 M4 x 99.ipt").write_bytes(b"old")

    root = make_workspace(tmp_path / "PIHTI")
    frame = root / "Frame" / "frame.iam"
    frame.write_bytes(
        reference_bytes(
            "C:\\Templates\\Standard (mm).iam",
            "C:\\CC\\ISO 4762\\ISO 4762 M4 x 12.ipt",
            "C:\\Frame\\parts\\old.ipt",
        )
    )
    mirror = checked_mirror(root)
    assert mirror.blocker("Frame/frame.iam") is None

    frame.write_bytes(reference_bytes("C:\\CC\\ISO 4762\\ISO 4762 M4 x 99.ipt"))
    assert mirror.blocker("Frame/frame.iam") == (
        "ISO 4762 M4 x 99.ipt",
        "ISO 4762 M4 x 99.ipt is missing",
    )
    # A size placed later is seen once the folder's times change.
    newer = library / "JIS B 1176"
    newer.mkdir()
    (newer / "JIS B 1176 - M3 x 16 - 0.5.ipt").write_bytes(b"screw")
    frame.write_bytes(reference_bytes("C:\\CC\\JIS B 1176 - M3 x 16 - 0.5.ipt"))
    assert mirror.blocker("Frame/frame.iam") is None


def test_the_folder_name_cache_walks_again_only_when_the_folder_changes(
    tmp_path: Path, monkeypatch
) -> None:
    folder = tmp_path / "Content Center Files"
    (folder / "R2027" / "en-US" / "ISO 4762").mkdir(parents=True)
    walks: list[Path] = []
    real = step_mirror._names_under
    monkeypatch.setattr(
        step_mirror, "_names_under", lambda path: walks.append(path) or real(path)
    )
    now = [0.0]
    assert step_mirror.folder_names(folder, clock=lambda: now[0]) == frozenset()
    assert step_mirror.folder_names(folder, clock=lambda: now[0]) == frozenset()
    assert len(walks) == 1

    deep = folder / "R2027" / "en-US" / "ISO 4762" / "ISO 4762 M4 x 12.ipt"
    deep.write_bytes(b"screw")  # the family folder is below the stamped levels
    assert step_mirror.folder_names(folder, clock=lambda: now[0]) == frozenset()
    now[0] = step_mirror.OUTSIDE_RECHECK_SECONDS + 1
    assert step_mirror.folder_names(folder, clock=lambda: now[0]) == {"iso 4762 m4 x 12.ipt"}
    assert len(walks) == 2


PROJECT_XML = """<?xml version="1.0" encoding="utf-16" standalone="no" ?>
<InventorProject schemarevid="14">
  <ProjectPaths>
    <ProjectPath pathtype="Workspace"><PathName>Workspace</PathName><Path>.</Path></ProjectPath>
    <ProjectPath pathtype="Library"><PathName>Vendor</PathName><Path>..\\Vendor Library</Path></ProjectPath>
  </ProjectPaths>
  <FolderOptions>
    <ContentCenterFolder>
      <Path>%PIHTI_TEST_SHARE%\\Content Center Files</Path>
      <ContentCenterConfig><ConfiguredLibraries>
        <Library DisplayName="Inventor ISO" ServerName="localhost"/>
      </ConfiguredLibraries></ContentCenterConfig>
    </ContentCenterFolder>
  </FolderOptions>
</InventorProject>
"""


def test_the_project_file_names_its_content_center_and_library_folders(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "PIHTI"
    workspace.mkdir()
    project = workspace / "PIHTI.ipj"
    project.write_bytes(b"\xff\xfe" + PROJECT_XML.encode("utf-16-le"))  # as Inventor writes it
    monkeypatch.setenv("PIHTI_TEST_SHARE", str(tmp_path / "share"))

    content_center, libraries = step_mirror.project_folders(project)
    assert content_center == tmp_path / "share" / "Content Center Files"
    assert libraries == (workspace / ".." / "Vendor Library",)
    assert step_mirror.project_file(workspace) == project

    # The live PIHTI.ipj names libraries only, no folder: nothing is invented.
    bare = tmp_path / "bare.ipj"
    bare.write_bytes(
        "<?xml version=\"1.0\"?><InventorProject><FolderOptions><ContentCenterFolder>"
        "<ContentCenterConfig/></ContentCenterFolder></FolderOptions></InventorProject>".encode()
    )
    assert step_mirror.project_folders(bare) == (None, ())
    empty = tmp_path / "empty.ipj"
    empty.write_bytes(b"")
    assert step_mirror.project_folders(empty) == (None, ())
    assert step_mirror.project_folders(tmp_path / "absent.ipj") == (None, ())


def test_the_content_center_folder_is_found_in_order(tmp_path: Path) -> None:
    workspace = tmp_path / "PIHTI"
    workspace.mkdir()
    profile = tmp_path / "profile"
    public = tmp_path / "public"
    per_user = profile / "Documents" / "Inventor" / "Content Center Files"
    shared = {
        version: public / "Documents" / "Autodesk" / f"Inventor {version}" / "Content Center Files"
        for version in ("2026", "2027")
    }
    environ = {"USERPROFILE": str(profile), "PUBLIC": str(public)}

    assert step_mirror.content_center_folder(workspace, environ) is None
    for folder in shared.values():
        folder.mkdir(parents=True)
    assert step_mirror.content_center_folder(workspace, environ) == shared["2027"]
    per_user.mkdir(parents=True)
    assert step_mirror.content_center_folder(workspace, environ) == per_user

    named = tmp_path / "share" / "CC"
    named.mkdir(parents=True)
    (workspace / "PIHTI.ipj").write_text(
        f"<InventorProject><FolderOptions><ContentCenterFolder><Path>{named}</Path>"
        "</ContentCenterFolder></FolderOptions></InventorProject>",
        encoding="utf-8",
    )
    assert step_mirror.content_center_folder(workspace, environ) == named

    override = {**environ, step_mirror.CONTENT_CENTER_ENV: str(tmp_path / "elsewhere")}
    assert step_mirror.content_center_folder(workspace, override) == tmp_path / "elsewhere"


def test_cli_status_names_a_plainly_missing_part(tmp_path: Path, capsys) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    frame = root / "Frame" / "frame.iam"
    frame.write_bytes(
        reference_bytes(
            "C:\\Templates\\Standard (mm).iam",
            "C:\\Users\\student\\OneDrive\\ICF70FLMG4MBA.ipt",
            "C:\\old\\Frame\\parts\\old.ipt",
        )
    )

    assert cli.main(["step-mirror", "status", str(root)]) == 0

    out = capsys.readouterr().out
    assert "need Doctor: 1\n  frame.iam: ICF70FLMG4MBA.ipt is missing  (Frame)\n" in out


def make_blocked_workspace(root: Path) -> Path:
    """`make_workspace`, with frame.iam naming a board.ipt that exists twice."""

    root = make_workspace(root)
    frame = root / "Frame" / "frame.iam"
    frame.write_bytes(
        reference_bytes("C:\\old\\Frame\\parts\\old.ipt", "C:\\old\\Frame\\board.ipt")
    )
    stamp(frame, BASE + 300 * SECOND)
    for folder in ("Boards/a", "Boards/b"):
        board = root / folder / "board.ipt"
        board.parent.mkdir(parents=True)
        board.write_bytes(b"board")
        stamp(board, BASE + 500 * SECOND)
    return root


def checked_mirror(root: Path) -> StepMirror:
    return StepMirror(
        root,
        where_used=lambda: build_index(root),
        locations=lambda: filename_locations(root),
        settled=lambda: (),
    )


def log_lines(mirror: StepMirror) -> list[list[str]]:
    return [line.split("\t") for line in mirror.log_path.read_text(encoding="utf-8").splitlines()]


def spy_on_export_copy(monkeypatch) -> list[str]:
    opened: list[str] = []
    real = inventor_session.export_copy

    def spy(session, source, target, **kwargs):
        opened.append(Path(source).name)
        return real(session, source, target, **kwargs)

    monkeypatch.setattr(inventor_session, "export_copy", spy)
    return opened


def test_export_never_opens_an_assembly_that_would_make_inventor_ask(
    tmp_path: Path, monkeypatch
) -> None:
    root = make_blocked_workspace(tmp_path / "PIHTI")
    mirror = checked_mirror(root)
    app = fake_for(root)
    opened = spy_on_export_copy(monkeypatch)

    result = mirror.export(fake_session(app), "Frame/frame.iam")

    assert result.outcome == step_mirror.NEEDS_DOCTOR
    assert result.reason == "board.ipt exists twice"
    assert opened == [] and not any(entry[0] == "open" for entry in app.log)
    assert not mirror.target("Frame/frame.iam").exists()
    assert mirror.blocker("Frame/frame.iam") == ("board.ipt", "board.ipt exists twice")
    assert mirror.blocker("Frame/parts/old.ipt") is None  # parts never ask

    forced = mirror.export(fake_session(app), "Frame/frame.iam", force=True)
    assert forced.exported and opened == ["frame.iam"]

    # Without where-used data nothing is checked, as before the pre-check.
    assert StepMirror(root).blocker("Frame/frame.iam") is None


def test_cli_sync_skips_a_needs_doctor_assembly_and_lists_it_at_the_end(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = make_blocked_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    monkeypatch.setattr(inventor_session, "connect", lambda **_: fake_session(app))
    opened = spy_on_export_copy(monkeypatch)

    code = cli.main(["step-mirror", "sync", str(root)])

    out = capsys.readouterr().out
    assert code == 0  # a skip is not a failure, like a file open in Inventor
    assert "frame.iam" not in opened and len(opened) == 5
    assert re.search(r"^Frame  1 needs Doctor  \d+\.\d s$", out, re.M)
    assert re.search(r"^Boards/a  1 exported  \d+\.\d s$", out, re.M)
    assert "exported 5 · not exported 0 · not started 0 · 1 needs Doctor" in out
    assert "need Doctor: 1\n  frame.iam: board.ipt exists twice  (Frame)\n" in out
    assert "--force" in out
    doctor = [line for line in log_lines(StepMirror(root)) if line[1] == step_mirror.NEEDS_DOCTOR]
    assert doctor and doctor[0][3:] == ["Frame/frame.iam", "board.ipt exists twice"]

    status = StepMirror(root).status(inventory_of(root))
    assert [item.path for item in status.queue] == ["Frame/frame.iam"]

    assert cli.main(["step-mirror", "status", str(root)]) == 0
    out = capsys.readouterr().out
    assert "need Doctor: 1\n  frame.iam: board.ipt exists twice  (Frame)\n" in out


def test_cli_export_refuses_a_needs_doctor_assembly_unless_forced(
    tmp_path: Path, monkeypatch, capsys, step_mirror_folder: Path
) -> None:
    root = make_blocked_workspace(tmp_path / "PIHTI")
    monkeypatch.setattr(inventor_session, "connect", lambda **_: fake_session(fake_for(root)))

    assert cli.main(["step-mirror", "export", str(root), "Frame/frame.iam"]) == 1
    out = capsys.readouterr().out
    assert "needs-doctor" in out and "board.ipt exists twice" in out and "--force" in out
    assert not (step_mirror_folder / "Frame" / "frame.iam.step").exists()

    assert cli.main(["step-mirror", "export", str(root), "Frame/frame.iam", "--force"]) == 0
    assert (step_mirror_folder / "Frame" / "frame.iam.step").is_file()


def test_the_job_passes_a_needs_doctor_assembly_over_until_the_name_is_settled(
    tmp_path: Path,
) -> None:
    root = make_blocked_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    session = fake_session(app)
    mirror = checked_mirror(root)
    job = MirrorJob(
        mirror,
        inventory=lambda: inventory_of(root),
        session=lambda: session,
        clock=Clock(),
        spacing_seconds=0.0,
        threaded=False,
    )

    order = [job.step().source.name for _ in range(4)]
    # frame.iam costs no tick: recorded, then the same tick moves on to new.ipt.
    assert order == ["old.ipt", "mid.ipt", "new.ipt", "board.ipt"]
    assert job.needs_doctor() == {"frame/frame.iam": "board.ipt exists twice"}
    assert job.deferred() == {}

    assert job.step().source.name == "board.ipt"  # the second copy
    assert job.step() is None
    assert job.step() is None
    doctor = [line for line in log_lines(mirror) if line[1] == step_mirror.NEEDS_DOCTOR]
    assert len(doctor) == 1, "a passed-over assembly is logged once, not every tick"
    assert not any(entry[:2] == ("open", "frame.iam") for entry in app.log)

    # Doctor removes the second copy: the reason is gone and the job exports it.
    (root / "Boards" / "b" / "board.ipt").unlink()
    assert job.step().source.name == "frame.iam"
    assert mirror.status(inventory_of(root)).queue == ()


def test_the_mirror_page_lists_needs_doctor_with_a_doctor_link(tmp_path: Path) -> None:
    root = make_blocked_workspace(tmp_path / "PIHTI")
    client = create_app(root).test_client()

    page = client.get("/step-mirror").get_data(as_text=True)
    section = page.split('id="sec-doctor"', 1)[1].split("</section>", 1)[0]
    assert "<h2>Needs Doctor</h2>" in section and "<strong>1</strong>" in section
    assert 'href="/doctor/name/board.ipt?assembly=Frame/frame.iam"' in section
    assert "<strong>frame.iam</strong>" in section and "board.ipt exists twice" in section
    assert "<dt>Need Doctor</dt><dd>1</dd>" in page
    assert 'href="#sec-doctor"' in page
    assert client.get("/doctor/name/board.ipt?assembly=Frame/frame.iam").status_code == 200

    clean = create_app(make_workspace(tmp_path / "Clean")).test_client()
    clean_page = clean.get("/step-mirror").get_data(as_text=True)
    section = clean_page.split('id="sec-doctor"', 1)[1].split("</section>", 1)[0]
    assert '<p class="doctor-empty">None</p>' in section


def test_export_now_on_a_needs_doctor_assembly_says_so(tmp_path: Path) -> None:
    root = make_blocked_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    viewer = create_app(root, session_factory=lambda: fake_session(app))
    done = viewer.test_client().post(
        "/part/Frame/frame.iam/step-export",
        data={"token": viewer.config["FORM_TOKEN"], "origin": "part"},
        follow_redirects=True,
    )
    html = done.get_data(as_text=True)
    assert "STEP not exported: frame.iam names a missing or repeated file; see Doctor" in html
    assert not any(entry[:2] == ("open", "frame.iam") for entry in app.log)


# ---- the printout and the log -----------------------------------------------


def test_cli_sync_verbose_prints_one_line_per_file(tmp_path: Path, monkeypatch, capsys) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    monkeypatch.setattr(inventor_session, "connect", lambda **_: fake_session(fake_for(root)))

    assert cli.main(["step-mirror", "sync", str(root), "--verbose"]) == 0
    out = capsys.readouterr().out
    for relative in ("Frame\\frame.iam", "Frame\\parts\\old.ipt", "Frame\\parts\\new.ipt"):
        assert re.search(rf"^exported\s+\d+\.\d\ds  {re.escape(relative)}$", out, re.M)
    assert not re.search(r"^Frame/parts  ", out, re.M)
    assert "exported 4 · not exported 0 · not started 0 · 0 need Doctor" in out


def test_every_attempt_is_logged_with_its_full_path(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    app.fail_export.add(str(root / "Frame/parts/mid.ipt").casefold())
    mirror = StepMirror(root)
    session = fake_session(app)

    mirror.export(session, "Frame/parts/old.ipt")
    mirror.export(session, "Frame/parts/mid.ipt")
    mirror.log_attempt("Frame/frame.iam", SKIPPED_OPEN)

    lines = log_lines(mirror)
    assert [line[1:2] + line[3:] for line in lines] == [
        ["exported", "Frame/parts/old.ipt", "Frame/parts/old.ipt.step"],
        ["failed", "Frame/parts/mid.ipt", "the translator failed"],
        [SKIPPED_OPEN, "Frame/frame.iam", "open in Inventor"],
    ]
    assert all(
        re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", line[0]) for line in lines
    )
    assert all(re.fullmatch(r"\d+\.\d\d", line[2]) for line in lines)
    assert str(root).casefold() not in mirror.log_path.read_text(encoding="utf-8").casefold()

    # The page's "Last exports" reads the end of the log, newest first.
    recent = mirror.recent()
    assert [line["path"] for line in recent] == [
        "Frame/frame.iam",
        "Frame/parts/mid.ipt",
        "Frame/parts/old.ipt",
    ]
    assert recent[1]["outcome"] == "failed: the translator failed"
    assert recent[0]["kind"] == SKIPPED_OPEN


def test_the_log_rotates_at_five_megabytes_and_keeps_one(
    tmp_path: Path, step_mirror_folder: Path
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    mirror = StepMirror(root)
    mirror.ensure_root()
    old = step_mirror_folder / "export.log.1"
    old.write_text("older\n", encoding="utf-8")
    mirror.log_path.write_bytes((b"x" * 99 + b"\n") * (step_mirror.LOG_ROTATE_BYTES // 100 + 1))

    mirror.log_attempt("Frame/parts/old.ipt", TIMED_OUT, 10.0)

    assert old.stat().st_size >= step_mirror.LOG_ROTATE_BYTES  # the full log, not "older"
    lines = log_lines(mirror)
    assert len(lines) == 1 and lines[0][1] == TIMED_OUT
    assert sorted(path.name for path in step_mirror_folder.glob("export.log*")) == [
        "export.log",
        "export.log.1",
    ]

    # Below the limit nothing rotates.
    mirror.log_attempt("Frame/parts/mid.ipt", EXPORTED)
    assert len(log_lines(mirror)) == 2


def test_the_log_is_never_written_before_the_mirror_exists(
    tmp_path: Path, step_mirror_folder: Path
) -> None:
    mirror = StepMirror(make_workspace(tmp_path / "PIHTI"))
    mirror.log_attempt("Frame/parts/old.ipt", EXPORTED)
    assert not step_mirror_folder.exists()
    assert mirror.recent() == []


# ---- leftovers from a timeout -----------------------------------------------


def leave_open(app: FakeInventor, root: Path, relative: str) -> None:
    """What a timed-out export leaves: the document loaded, without a window."""

    app.Documents.Open(str(root / relative), False)


def record_timeout(mirror: StepMirror, relative: str) -> None:
    mirror.ensure_root()
    source = mirror.workspace / relative
    mirror._record(
        relative,
        source.stat(),
        inventor_session.ExportResult(source, mirror.target(relative), TIMED_OUT, 10.0),
    )


def test_a_timeout_records_the_document_it_may_have_left_open(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    app.hang = ("saveas", str(root / "Frame/parts/old.ipt").casefold())
    mirror = StepMirror(root)
    try:
        result = mirror.export(fake_session(app), "Frame/parts/old.ipt", timeout=0.2)
    finally:
        app.release.set()
    assert result.outcome == TIMED_OUT
    assert mirror.pending_close() == ["Frame/parts/old.ipt"]
    raw = mirror.pending_close_path.read_text(encoding="utf-8")
    assert str(root).casefold() not in raw.casefold()


def test_sync_closes_a_leftover_without_a_window_first(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root, owner_open=["Frame/parts/new.ipt"])
    mirror = StepMirror(root)
    record_timeout(mirror, "Frame/frame.iam")
    leave_open(app, root, "Frame/frame.iam")
    monkeypatch.setattr(inventor_session, "connect", lambda **_: fake_session(app))

    assert cli.main(["step-mirror", "sync", str(root)]) == 0

    out = capsys.readouterr().out
    assert "closed a leftover from an earlier timeout: Frame\\frame.iam" in out
    assert "frame.iam: open in Inventor" not in out  # closed, then exported
    assert ("close", "frame.iam", True) in app.log
    assert app.violations == []  # the owner's new.ipt was never touched
    assert mirror.pending_close() == [] and not mirror.pending_close_path.exists()
    closed = [line for line in log_lines(mirror) if line[1] == step_mirror.CLOSED_LEFTOVER]
    assert [line[3] for line in closed] == ["Frame/frame.iam"]
    assert mirror.target("Frame/frame.iam").is_file()


def test_a_leftover_with_a_window_is_the_owners_and_stays_recorded(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    mirror = StepMirror(root)
    record_timeout(mirror, "Frame/frame.iam")
    record_timeout(mirror, "Frame/parts/old.ipt")
    leave_open(app, root, "Frame/frame.iam")
    app.windows.append(str(root / "Frame" / "FRAME.iam"))  # the owner opened it since

    assert mirror.close_leftovers(fake_session(app)) == []
    assert not any(entry[0] == "close" for entry in app.log)
    # old.ipt is no longer held, so there is nothing to close and its record goes.
    assert mirror.pending_close() == ["Frame/frame.iam"]

    app.windows.clear()
    assert mirror.close_leftovers(fake_session(app)) == ["Frame/frame.iam"]
    assert mirror.pending_close() == []


def test_a_leftover_stays_recorded_until_its_close_succeeds(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    mirror = StepMirror(root)
    record_timeout(mirror, "Frame/frame.iam")
    leave_open(app, root, "Frame/frame.iam")
    app.fail_close.add(str(root / "Frame/frame.iam").casefold())

    assert mirror.close_leftovers(fake_session(app)) == []
    assert mirror.pending_close() == ["Frame/frame.iam"]

    app.fail_close.clear()
    assert mirror.close_leftovers(fake_session(app)) == ["Frame/frame.iam"]
    assert mirror.pending_close() == [] and app.ours() == []


def test_a_leftover_another_open_document_uses_is_left_alone(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    part = str(root / "Frame" / "parts" / "old.ipt")
    app.disk[str(root / "Frame" / "frame.iam").casefold()] = [part]
    mirror = StepMirror(root)
    record_timeout(mirror, "Frame/parts/old.ipt")
    leave_open(app, root, "Frame/parts/old.ipt")
    leave_open(app, root, "Frame/frame.iam")  # an assembly holding the part

    assert mirror.close_leftovers(fake_session(app)) == []
    assert mirror.pending_close() == ["Frame/parts/old.ipt"]


def test_the_job_closes_leftovers_on_its_tick(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    job, mirror = job_for(root, app, Clock())
    record_timeout(mirror, "Frame/parts/old.ipt")
    leave_open(app, root, "Frame/parts/old.ipt")

    assert job.step().source.name == "old.ipt"  # closed first, so not "open in Inventor"
    assert mirror.pending_close() == [] and app.ours() == []


# ---- "Export fresh STEPs": the on-demand batch ------------------------------


def batch_for(root: Path, *, mirror: StepMirror | None = None, threaded: bool = False):
    mirror = mirror or StepMirror(root)
    batch = step_mirror.MirrorBatch(
        mirror, inventory=lambda: inventory_of(root), threaded=threaded, per_file_timeout=5.0
    )
    return batch, mirror


def wait_for(condition, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out waiting"
        time.sleep(0.01)


def hang_on(app: FakeInventor, root: Path, relative: str) -> None:
    app.hang = ("saveas", str(root / relative).casefold())


def hanging(app: FakeInventor, name: str) -> bool:
    return ("hang", name) in list(app.log)


def test_export_many_stops_between_files_when_asked(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    names = ("old", "mid", "new")
    pairs = [(root / f"Frame/parts/{name}.ipt", tmp_path / f"{name}.ipt.step") for name in names]
    asked: list[int] = []

    def should_stop() -> bool:
        asked.append(1)
        return len(asked) > 1  # after the first file

    results = inventor_session.export_many(
        fake_session(fake_for(root)), pairs, should_stop=should_stop
    )
    assert [result.source.stem for result in results] == ["old"]
    assert results.stopped_because == inventor_session.STOP_REQUESTED


def test_the_batch_exports_every_stale_and_missing_file_oldest_first(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root, owner_open=["Frame/parts/mid.ipt"])
    batch, mirror = batch_for(root)
    assert batch.status()["state"] == "idle" and batch.status()["line"] == ""
    mirror.ensure_root()  # a skip is logged only into an existing mirror, as in `sync`

    assert batch.start(fake_session(app)) is True

    assert app.violations == []
    opened = [entry[1] for entry in app.log if entry[0] == "open"]
    assert opened == ["old.ipt", "frame.iam", "new.ipt"]
    status = batch.status()
    assert status["state"] == "finished" and not status["running"]
    assert (status["total"], status["done"], status["exported"]) == (3, 3, 3)
    assert status["open_in_inventor"] == 1
    assert status["line"] == "Finished · exported 3 of 3 · 1 open in Inventor"
    # One export.log line per file, the open one included.
    kinds = {line[3]: line[1] for line in log_lines(mirror)}
    assert kinds == {
        "Frame/parts/mid.ipt": SKIPPED_OPEN,
        "Frame/parts/old.ipt": EXPORTED,
        "Frame/frame.iam": EXPORTED,
        "Frame/parts/new.ipt": EXPORTED,
    }
    assert len(mirror.status(inventory_of(root)).current) == 3


def test_the_batch_closes_leftovers_first_and_skips_needs_doctor(
    tmp_path: Path, monkeypatch
) -> None:
    root = make_blocked_workspace(tmp_path / "PIHTI")
    mirror = checked_mirror(root)
    app = fake_for(root)
    record_timeout(mirror, "Frame/parts/old.ipt")
    leave_open(app, root, "Frame/parts/old.ipt")
    opened = spy_on_export_copy(monkeypatch)
    batch, _mirror = batch_for(root, mirror=mirror)

    batch.start(fake_session(app))

    assert ("close", "old.ipt", True) in app.log and mirror.pending_close() == []
    assert "frame.iam" not in opened and "old.ipt" in opened
    status = batch.status()
    assert status["needs_doctor"] == 1 and status["exported"] == status["total"] - 1
    assert "1 needs Doctor" in status["line"]
    doctor = [line for line in log_lines(mirror) if line[1] == step_mirror.NEEDS_DOCTOR]
    assert [line[3] for line in doctor] == ["Frame/frame.iam"]


def test_a_second_start_while_the_batch_runs_does_nothing(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    hang_on(app, root, "Frame/parts/old.ipt")
    batch, _mirror = batch_for(root, threaded=True)
    try:
        assert batch.start(fake_session(app)) is True
        wait_for(lambda: hanging(app, "old.ipt"))
        assert batch.active()
        running = batch.status()
        assert running["state"] == "running" and running["line"] == "Exporting 1 of 4 · old.ipt"
        assert batch.start(fake_session(app)) is False
    finally:
        app.release.set()
    assert batch.wait(10)
    assert batch.status()["exported"] == 4
    assert [entry[1] for entry in app.log if entry[0] == "open"].count("old.ipt") == 1


def test_stop_ends_the_batch_after_the_file_in_progress(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    hang_on(app, root, "Frame/parts/old.ipt")
    batch, mirror = batch_for(root, threaded=True)
    assert batch.stop() is False  # nothing runs yet
    try:
        batch.start(fake_session(app))
        wait_for(lambda: hanging(app, "old.ipt"))
        assert batch.stop() is True
        stopping = batch.status()
        assert stopping["state"] == "stopping" and stopping["running"]
        assert stopping["line"] == "Stopping after this file · 0 of 4 done"
    finally:
        app.release.set()
    assert batch.wait(10)
    status = batch.status()
    assert status["state"] == "stopped" and status["reason"] == inventor_session.STOP_REQUESTED
    assert status["line"] == "Stopped · exported 1 of 4"
    assert mirror.target("Frame/parts/old.ipt").is_file()
    assert not mirror.target("Frame/parts/mid.ipt").exists()
    # A new start begins afresh.
    assert batch.start(fake_session(app)) is True and batch.wait(10)
    assert batch.status()["line"] == "Finished · exported 3 of 3"


def test_the_batch_stops_with_the_reason_when_inventor_stops_answering(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    hang_on(app, root, "Frame/parts/old.ipt")
    batch, _mirror = batch_for(root)
    batch.per_file_timeout = 0.2
    try:
        batch.start(fake_session(app))
    finally:
        app.release.set()
    status = batch.status()
    assert status["state"] == "stopped" and status["reason"] == inventor_session.NOT_ANSWERING
    assert status["line"] == (
        f"Stopped: {inventor_session.NOT_ANSWERING} · exported 0 of 4 · 1 not exported"
    )
    assert status["last"] == "old.ipt: timeout"


def test_the_job_yields_while_a_batch_runs(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    job, mirror = job_for(root, app, Clock())
    busy = [True]
    job.yield_to = lambda: busy[0]

    assert job.step() is None
    assert app.log == [] and not mirror.root.exists()
    busy[0] = False
    assert job.step().exported


# ---- the batch in the viewer ------------------------------------------------


def mirror_card(html: str) -> str:
    return html.split('id="mirror-batch"', 1)[1].split("</section>", 1)[0]


def test_without_inventor_the_page_asks_for_it_and_starts_nothing(
    tmp_path: Path, step_mirror_folder: Path
) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    viewer = create_app(root)
    client = viewer.test_client()

    card = mirror_card(client.get("/step-mirror").get_data(as_text=True))
    assert "Start Inventor, open PIHTI.ipj, then come back" in card
    assert "Export fresh STEPs" not in card and "step-mirror/export" not in card

    token = viewer.config["FORM_TOKEN"]
    assert client.post("/step-mirror/export", data={}).status_code == 403
    done = client.post("/step-mirror/export", data={"token": token})
    assert done.status_code == 302
    assert done.headers["Location"] == "/step-mirror?batch=absent#mirror-batch"
    page = client.get("/step-mirror?batch=absent").get_data(as_text=True)
    assert "Inventor is not running; nothing started." in mirror_card(page)
    assert viewer.extensions["pihti_step_mirror_batch"].status()["state"] == "idle"
    assert not step_mirror_folder.exists()


def test_the_page_starts_a_batch_and_reports_it_as_json(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    viewer = create_app(root, session_factory=lambda: fake_session(app))
    client = viewer.test_client()
    token = viewer.config["FORM_TOKEN"]
    batch = viewer.extensions["pihti_step_mirror_batch"]

    card = mirror_card(client.get("/step-mirror").get_data(as_text=True))
    assert 'action="/step-mirror/export"' in card and f'name="token" value="{token}"' in card
    assert '<button class="copy-path" type="submit">Export fresh STEPs</button>' in card
    assert "4 waiting" in card and 'data-batch-status="/step-mirror/status"' in card
    assert "Start Inventor" not in card

    idle = client.get("/step-mirror/status").get_json()
    assert idle["state"] == "idle" and idle["running"] is False
    assert idle["counts"] == {"current": 0, "stale": 0, "missing": 4, "total": 4}

    done = client.post("/step-mirror/export", data={"token": token})
    assert done.status_code == 302 and done.headers["Location"] == "/step-mirror#mirror-batch"
    assert batch.wait(10)

    status = client.get("/step-mirror/status").get_json()
    assert set(status) == {
        "state", "running", "total", "done", "exported", "not_exported", "needs_doctor",
        "open_in_inventor", "current", "reason", "last", "line", "counts",
    }
    assert status["state"] == "finished" and status["running"] is False
    assert (status["total"], status["exported"], status["line"]) == (
        4, 4, "Finished · exported 4 of 4"
    )
    assert status["counts"] == {"current": 4, "stale": 0, "missing": 0, "total": 4}
    page = client.get("/step-mirror").get_data(as_text=True)
    assert "Finished · exported 4 of 4" in mirror_card(page)
    assert "Nothing to export." in mirror_card(page)

    script = client.get("/static/dedup.js").get_data(as_text=True)
    assert "[data-mirror-batch]" in script and "var POLL_MS = 3000;" in script


def test_the_page_answers_a_second_start_and_a_stop_with_a_notice(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    hang_on(app, root, "Frame/parts/old.ipt")
    viewer = create_app(root, session_factory=lambda: fake_session(app))
    client = viewer.test_client()
    token = viewer.config["FORM_TOKEN"]
    batch = viewer.extensions["pihti_step_mirror_batch"]
    batch.per_file_timeout = 5.0

    assert client.post("/step-mirror/stop", data={"token": token}).headers["Location"] == (
        "/step-mirror?batch=idle#mirror-batch"
    )
    try:
        client.post("/step-mirror/export", data={"token": token})
        wait_for(lambda: hanging(app, "old.ipt"))
        page = mirror_card(client.get("/step-mirror").get_data(as_text=True))
        assert 'data-batch-state="running"' in page and "Exporting 1 of 4 · old.ipt" in page
        assert re.search(r'<form[^>]*data-batch-start hidden>', page)
        assert 'action="/step-mirror/stop"' in page and "Stop after this file" in page

        again = client.post("/step-mirror/export", data={"token": token})
        assert again.headers["Location"] == "/step-mirror?batch=running#mirror-batch"
        assert "A batch is already running." in client.get("/step-mirror?batch=running").get_data(
            as_text=True
        )

        # Export now on a file page waits for the batch instead of timing out.
        busy = client.post(
            "/part/Frame/frame.iam/step-export", data={"token": token, "origin": "part"},
            follow_redirects=True,
        )
        assert "STEP not exported: the batch export is running" in busy.get_data(as_text=True)

        stop = client.post("/step-mirror/stop", data={"token": token})
        assert stop.headers["Location"] == "/step-mirror#mirror-batch"
        assert client.get("/step-mirror/status").get_json()["state"] == "stopping"
    finally:
        app.release.set()
    assert batch.wait(10)
    assert client.get("/step-mirror/status").get_json()["line"] == "Stopped · exported 1 of 4"


def test_the_viewer_job_yields_to_the_page_batch(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "PIHTI")
    app = fake_for(root)
    hang_on(app, root, "Frame/parts/old.ipt")
    viewer = create_app(root, refresh_seconds=5, session_factory=lambda: fake_session(app))
    job = viewer.extensions["pihti_step_mirror_job"]
    batch = viewer.extensions["pihti_step_mirror_batch"]
    assert batch.job is job
    try:
        # Started directly: a request would also start the snapshot ticker.
        batch.start(fake_session(app))
        wait_for(lambda: hanging(app, "old.ipt"))
        assert job.step() is None
    finally:
        app.release.set()
    assert batch.wait(10)
    assert [entry[1] for entry in app.log if entry[0] == "open"] == [
        "old.ipt", "mid.ipt", "frame.iam", "new.ipt"
    ]
