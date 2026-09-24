import sys
import time
from pathlib import Path

import pytest
from inventor_fake import FakeInventor, fake_session

from pihti_dedup import inventor_session
from pihti_dedup.inventor_session import (
    NO_ANSWER,
    NO_DESCRIPTOR,
    REPAIRED,
    SKIPPED_OPEN,
    RepairRefused,
    Session,
    SessionTimeout,
    plan_repair,
    repair_references,
)

# Bound before the suite-wide guard replaces the module attribute.
REAL_CONNECT = inventor_session.connect


def make_disk(root: Path) -> tuple[Path, Path, Path, dict]:
    part = root / "parts" / "Body.ipt"
    part.parent.mkdir(parents=True)
    part.write_bytes(b"geometry")
    first = root / "probe.iam"
    second = root / "stand.iam"
    other = root / "parts" / "shaft.ipt"
    other.write_bytes(b"geometry")
    disk = {first: [str(part), str(other)], second: [str(part)]}
    return part, first, second, disk


def renamer(part: Path, new: Path, calls: list, app: FakeInventor | None = None):
    def rename() -> None:
        calls.append("rename")
        if app is not None:
            app.log.append(("rename",))
        part.rename(new)

    return rename


def test_repair_opens_renames_repoints_saves_closes_and_verifies(tmp_path: Path) -> None:
    part, first, second, disk = make_disk(tmp_path)
    new = part.with_name("Bearing-housing.ipt")
    app = FakeInventor(disk)
    calls: list = []

    result = repair_references(
        fake_session(app), [first, second], part.name, new, rename=renamer(part, new, calls, app)
    )

    assert result.renamed and result.complete and not result.timed_out
    assert result.outcomes == ((first, REPAIRED), (second, REPAIRED))
    assert result.version == "2027.1"
    assert calls == ["rename"] and new.is_file() and not part.exists()
    # Open everything while the old name resolves, rename, repoint and save,
    # close without saving, then reopen each to verify.
    assert [entry[0] for entry in app.log] == [
        "open", "open", "rename",
        "replace", "save", "replace", "save",
        "close", "close",
        "open", "close", "open", "close",
    ]  # fmt: skip
    assert all(entry[2] is False for entry in app.log if entry[0] in {"open", "save"})
    assert [entry for entry in app.log if entry[0] == "replace"] == [
        ("replace", "probe.iam", "Bearing-housing.ipt"),
        ("replace", "stand.iam", "Bearing-housing.ipt"),
    ]
    assert all(entry[2] is True for entry in app.log if entry[0] == "close")
    # Only the Body.ipt reference changed; shaft.ipt was left alone.
    assert app.disk[str(first).casefold()] == [str(new), str(tmp_path / "parts" / "shaft.ipt")]
    # Reopened to verify, and nothing of ours is left loaded.
    assert [entry[1] for entry in app.log if entry[0] == "open"].count("probe.iam") == 2
    assert app.ours() == [] and app.violations == []


def test_a_document_open_in_the_owner_session_is_never_touched(tmp_path: Path) -> None:
    part, first, second, disk = make_disk(tmp_path)
    new = part.with_name("Housing.ipt")
    app = FakeInventor(disk, owner_open=[first])

    result = repair_references(
        fake_session(app), [first, second], part.name, new, rename=renamer(part, new, [])
    )

    assert result.outcomes == ((first, SKIPPED_OPEN), (second, REPAIRED))
    assert not result.complete
    assert app.violations == []
    assert all(entry[1] != "probe.iam" for entry in app.log if entry[0] != "hang")
    assert [document.name for document in app.loaded] == ["probe.iam"]


def test_a_referrer_without_a_matching_descriptor_is_closed_unsaved(tmp_path: Path) -> None:
    part, first, second, disk = make_disk(tmp_path)
    disk[second] = [str(tmp_path / "parts" / "shaft.ipt")]  # the name was only a fossil
    new = part.with_name("Housing.ipt")
    app = FakeInventor(disk)

    result = repair_references(
        fake_session(app), [first, second], part.name, new, rename=renamer(part, new, [])
    )

    assert dict(result.outcomes) == {first: REPAIRED, second: NO_DESCRIPTOR}
    assert result.complete
    assert ("save", "stand.iam", False) not in app.log
    assert ("close", "stand.iam", True) in app.log
    assert app.ours() == []


def test_a_failing_save_is_reported_and_the_document_is_discarded(tmp_path: Path) -> None:
    part, first, second, disk = make_disk(tmp_path)
    new = part.with_name("Housing.ipt")
    app = FakeInventor(disk)
    app.fail_save.add(str(second).casefold())

    result = repair_references(
        fake_session(app), [first, second], part.name, new, rename=renamer(part, new, [])
    )

    outcomes = dict(result.outcomes)
    assert outcomes[first] == REPAIRED
    assert outcomes[second] == "failed: the file is read-only"
    assert app.disk[str(second).casefold()] == [str(part)]
    assert ("close", "stand.iam", True) in app.log and app.ours() == []


def test_a_save_that_does_not_stick_fails_verification(tmp_path: Path) -> None:
    part, first, second, disk = make_disk(tmp_path)
    new = part.with_name("Housing.ipt")
    app = FakeInventor(disk)
    app.lose_save.add(str(first).casefold())

    result = repair_references(
        fake_session(app), [first], part.name, new, rename=renamer(part, new, [])
    )

    assert result.outcomes == ((first, "failed: still references Body.ipt after saving"),)


def test_a_reference_resolved_to_a_surviving_copy_is_left_alone(tmp_path: Path) -> None:
    part, first, second, disk = make_disk(tmp_path)
    survivor = tmp_path / "other" / "Body.ipt"
    survivor.parent.mkdir()
    survivor.write_bytes(b"other geometry")
    disk[second] = [str(survivor)]  # same filename, the other copy
    new = part.with_name("Housing.ipt")
    app = FakeInventor(disk)

    plan = plan_repair(fake_session(app), [first, second], part.name, survivors=[survivor])
    assert [item.state for item in plan.referrers] == [
        "will repoint 1 reference",
        "uses another file with the old name",
    ]
    result = repair_references(
        fake_session(app),
        [first, second],
        part.name,
        new,
        rename=renamer(part, new, []),
        survivors=[survivor],
    )

    assert result.outcomes == ((first, REPAIRED), (second, NO_DESCRIPTOR))
    # second was never applicable (it already used the surviving copy), so it
    # does not block completeness.
    assert result.complete
    assert app.disk[str(second).casefold()] == [str(survivor)]
    assert ("save", "stand.iam", False) not in app.log


def test_the_file_itself_open_in_inventor_refuses_before_anything_moves(tmp_path: Path) -> None:
    part, first, second, disk = make_disk(tmp_path)
    new = part.with_name("Housing.ipt")
    app = FakeInventor(disk, owner_open=[part])
    calls: list = []

    with pytest.raises(RepairRefused, match="close it first"):
        repair_references(
            fake_session(app), [first], part.name, new, rename=renamer(part, new, calls)
        )
    assert calls == [] and part.is_file()
    assert not any(entry[0] == "open" for entry in app.log)


def test_a_rename_that_fails_saves_nothing(tmp_path: Path) -> None:
    part, first, second, disk = make_disk(tmp_path)
    new = part.with_name("Housing.ipt")
    app = FakeInventor(disk)

    def refuse() -> None:
        raise PermissionError("the file is locked")

    with pytest.raises(PermissionError):
        repair_references(fake_session(app), [first, second], part.name, new, rename=refuse)
    assert not any(entry[0] in {"replace", "save"} for entry in app.log)
    assert app.ours() == []


def test_a_hang_before_the_rename_times_out_and_renames_nothing(tmp_path: Path) -> None:
    part, first, second, disk = make_disk(tmp_path)
    new = part.with_name("Housing.ipt")
    app = FakeInventor(disk)
    app.hang = ("open", str(second).casefold())
    calls: list = []
    session = fake_session(app)

    started = time.monotonic()
    result = repair_references(
        session, [first, second], part.name, new, rename=renamer(part, new, calls), timeout=0.3
    )
    assert time.monotonic() - started < 5
    assert result.timed_out and not result.renamed
    assert result.outcomes == ((first, f"failed: {NO_ANSWER}"), (second, f"failed: {NO_ANSWER}"))
    # While the worker is stuck, a second call fails at once instead of queueing.
    with pytest.raises(SessionTimeout):
        session.open_documents()

    app.release.set()
    deadline = time.monotonic() + 5
    while app.ours() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert calls == [] and part.is_file()
    assert app.ours() == []
    assert not any(entry[0] in {"replace", "save"} for entry in app.log)


def test_a_hang_after_the_rename_reports_it_and_saves_nothing_more(tmp_path: Path) -> None:
    part, first, second, disk = make_disk(tmp_path)
    new = part.with_name("Housing.ipt")
    app = FakeInventor(disk)
    app.hang = ("replace", str(first).casefold())

    result = repair_references(
        fake_session(app), [first, second], part.name, new, rename=renamer(part, new, []), timeout=0.3
    )
    assert result.timed_out and result.renamed
    assert all(outcome == f"failed: {NO_ANSWER}" for _, outcome in result.outcomes)

    app.release.set()
    deadline = time.monotonic() + 5
    while app.ours() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert app.ours() == []
    assert not any(entry[0] == "save" for entry in app.log)
    assert app.disk[str(first).casefold()][0] == str(part)


def test_plan_repair_reads_without_writing(tmp_path: Path) -> None:
    part, first, second, disk = make_disk(tmp_path)
    disk[second] = []
    third = tmp_path / "frame.iam"
    disk[third] = [str(part)]
    app = FakeInventor(disk, owner_open=[third])

    plan = plan_repair(fake_session(app), [first, second, third], part.name, target=part)

    states = {item.path: item.state for item in plan.referrers}
    assert states == {
        first: "will repoint 1 reference",
        second: "no reference to the old name",
        third: "open in Inventor: close it first",
    }
    assert plan.repairable == (first,) and not plan.target_open
    assert not any(entry[0] in {"replace", "save"} for entry in app.log)
    assert app.ours() == [] and app.violations == []


def test_open_documents_are_casefolded_full_paths(tmp_path: Path) -> None:
    app = FakeInventor({}, owner_open=[tmp_path / "Probe.IAM"])
    assert fake_session(app).open_documents() == {str(tmp_path / "probe.iam").casefold()}


def test_an_error_inside_the_worker_reaches_the_caller() -> None:
    def broken():
        raise RuntimeError("not registered")

    with pytest.raises(RuntimeError, match="not registered"):
        Session(broken).open_documents()


def test_connect_is_none_off_windows_without_importing_comtypes(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    before = set(sys.modules)
    assert REAL_CONNECT() is None
    assert not any(name.startswith("comtypes") for name in set(sys.modules) - before)


def test_the_suite_never_reaches_a_real_inventor() -> None:
    assert inventor_session.connect() is None
