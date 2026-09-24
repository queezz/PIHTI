"""Rename plus Inventor repair: ledger, where-used, the web forms, and the CLI.

Every session here is the fake from `inventor_fake`; the suite-wide guard in
`conftest.py` keeps `inventor_session.connect` answering None.
"""

import json
from pathlib import Path

import pytest
from inventor_fake import FakeDocument, FakeInventor, fake_session, reference_bytes

from pihti_dedup import cli, inventor_session
from pihti_dedup.renames import (
    RenameEntry,
    RenameError,
    execute_rename,
    ledger_path,
    plan_rename,
    read_ledger,
    set_settled,
)
from pihti_dedup.web import INVENTOR_ABSENT, create_app
from pihti_dedup.whereused import build_index


def make_workspace(root: Path) -> tuple[Path, FakeInventor]:
    """Body.ipt, named by two assemblies; the fake Inventor knows both."""

    root = root.resolve()
    parts = root / "Frame" / "parts"
    parts.mkdir(parents=True)
    part = parts / "Body.ipt"
    part.write_bytes(b"geometry")
    probe = root / "Frame" / "probe.iam"
    stand = root / "Frame" / "stand.iam"
    probe.write_bytes(reference_bytes(str(part)))
    stand.write_bytes(reference_bytes(str(part)))
    app = FakeInventor({probe: [str(part)], stand: [str(part)]})
    return root, app


def planned(root: Path, new_name: str = "Frame-body"):
    return plan_rename(root, "Frame/parts/Body.ipt", new_name, index=build_index(root))


# ---- renames.py ------------------------------------------------------------


def test_a_fully_repaired_rename_is_settled_and_will_not_prompt(tmp_path: Path) -> None:
    root, app = make_workspace(tmp_path)

    result = execute_rename(root, planned(root), session=fake_session(app))

    entry = result.entry
    assert (root / "Frame" / "parts" / "Frame-body.ipt").is_file()
    assert entry.repaired == ("Frame/probe.iam", "Frame/stand.iam")
    assert entry.fully_repaired and entry.settled and entry.will_prompt is False
    assert entry.repair_note == "repaired through Inventor 2027.1"
    assert read_ledger(root) == (entry,)
    line = json.loads(ledger_path(root).read_text(encoding="utf-8"))
    assert line["repaired"] == ["Frame/probe.iam", "Frame/stand.iam"]
    assert str(root).casefold() not in ledger_path(root).read_text(encoding="utf-8").casefold()


def test_a_partial_repair_stays_open_and_names_what_was_not_repaired(tmp_path: Path) -> None:
    root, app = make_workspace(tmp_path)
    app.loaded.append(FakeDocument(app, str(root / "Frame" / "stand.iam"), owner=True))

    entry = execute_rename(root, planned(root), session=fake_session(app)).entry

    assert entry.repaired == ("Frame/probe.iam",)
    assert not entry.fully_repaired and not entry.settled and entry.will_prompt is True
    assert entry.repair_note == (
        "repaired through Inventor 2027.1: Frame/probe.iam; "
        "not repaired: Frame/stand.iam (open in Inventor: close it first)"
    )


def test_no_answer_from_inventor_renames_nothing_and_writes_no_ledger(tmp_path: Path) -> None:
    root, app = make_workspace(tmp_path)
    app.hang = ("open", str(root / "Frame" / "probe.iam").casefold())
    try:
        with pytest.raises(RenameError, match="did not answer"):
            execute_rename(root, planned(root), session=fake_session(app), timeout=0.2)
    finally:
        app.release.set()
    assert (root / "Frame" / "parts" / "Body.ipt").is_file()
    assert read_ledger(root) == ()


def test_the_file_open_in_inventor_refuses_the_rename(tmp_path: Path) -> None:
    root, app = make_workspace(tmp_path)
    app.loaded.append(FakeDocument(app, str(root / "Frame" / "parts" / "Body.ipt"), owner=True))

    with pytest.raises(RenameError, match="close it first; nothing was renamed"):
        execute_rename(root, planned(root), session=fake_session(app))
    assert (root / "Frame" / "parts" / "Body.ipt").is_file() and read_ledger(root) == ()


def test_without_referrers_a_session_changes_nothing(tmp_path: Path) -> None:
    root, app = make_workspace(tmp_path)
    for name in ("probe.iam", "stand.iam"):
        (root / "Frame" / name).unlink()

    entry = execute_rename(root, planned(root), session=fake_session(app)).entry

    assert app.log == [] and entry.repaired == () and entry.repair_note == ""
    assert entry.settled is False


def test_ledger_lines_with_and_without_the_repair_keys_both_load(tmp_path: Path) -> None:
    path = ledger_path(tmp_path)
    path.parent.mkdir(parents=True)
    old = {
        "id": "a" * 16,
        "timestamp": "2026-08-05T00:00:00+00:00",
        "old_path": "A/x.ipt",
        "new_path": "A/y.ipt",
        "old_name": "x.ipt",
        "new_name": "y.ipt",
        "where_used": ["A/top.iam"],
        "will_prompt": True,
        "settled": False,
    }
    new = {**old, "id": "b" * 16, "repaired": ["A/top.iam"], "repair_note": "repaired through Inventor 2027.1"}
    path.write_text(json.dumps(old) + "\n" + json.dumps(new) + "\n", encoding="utf-8")

    first, second = read_ledger(tmp_path)
    assert first.repaired == () and first.repair_note == "" and not first.fully_repaired
    assert second.repaired == ("A/top.iam",) and second.fully_repaired
    assert RenameEntry.from_dict(second.to_dict()) == second
    # Rewriting the ledger keeps the keys on every line.
    set_settled(tmp_path, first.id, True)
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["repaired"] == [] and lines[1]["repaired"] == ["A/top.iam"]


# ---- where-used --------------------------------------------------------------


def test_a_repaired_referrer_stops_naming_the_fossil_old_name(tmp_path: Path) -> None:
    root, _ = make_workspace(tmp_path)
    # What Inventor leaves behind: the new name, and the old one as a fossil string.
    (root / "Frame" / "probe.iam").write_bytes(reference_bytes("parts\\Frame-body.ipt", "parts\\Body.ipt"))

    plain = build_index(root)
    settled = build_index(root, settled={("Frame\\probe.iam", "BODY.ipt")})

    assert plain.referring("Body.ipt") == ("Frame/probe.iam", "Frame/stand.iam")
    assert settled.referring("Body.ipt") == ("Frame/stand.iam",)
    assert settled.names_in("Frame/probe.iam") == ("Frame-body.ipt",)
    assert settled.referring("Frame-body.ipt") == ("Frame/probe.iam",)


# ---- web -------------------------------------------------------------------


def test_forms_without_inventor_say_so_and_offer_no_repair(tmp_path: Path) -> None:
    root, _ = make_workspace(tmp_path)
    client = create_app(root).test_client()

    doctor = client.get("/doctor/name/Body.ipt").get_data(as_text=True)
    part = client.get("/part/Frame/parts/Body.ipt").get_data(as_text=True)

    for html in (doctor, part):
        assert INVENTOR_ABSENT in html
        assert 'name="repair"' not in html
        assert "open in Inventor" not in html
    assert "never edits geometry, rewrites an Inventor reference" in part


def test_forms_with_inventor_offer_the_repair_and_flag_open_referrers(tmp_path: Path) -> None:
    root, app = make_workspace(tmp_path)
    app.loaded.append(FakeDocument(app, str(root / "Frame" / "stand.iam"), owner=True))
    session = fake_session(app)
    client = create_app(root, session_factory=lambda: session).test_client()

    for url in ("/doctor/name/Body.ipt", "/part/Frame/parts/Body.ipt"):
        html = client.get(url).get_data(as_text=True)
        assert (
            '<input type="checkbox" name="repair" value="1" checked> '
            "Repair references through Inventor 2027.1"
        ) in html
        assert html.count("open in Inventor: close it first") == 1
        assert INVENTOR_ABSENT not in html


def test_doctor_rename_confirms_then_repairs_and_the_ledger_settles(tmp_path: Path) -> None:
    root, app = make_workspace(tmp_path)
    session = fake_session(app)
    flask_app = create_app(root, session_factory=lambda: session)
    client = flask_app.test_client()
    form = {
        "token": flask_app.config["FORM_TOKEN"],
        "relative_path": "Frame/parts/Body.ipt",
        "new_name": "Frame-body",
        "repair": "1",
    }

    review = client.post("/doctor/name/Body.ipt", data=form)
    html = review.get_data(as_text=True)
    assert review.status_code == 409
    assert "Inventor opens, repoints, and saves 2 documents:" in html
    assert "<li><code>Frame\\probe.iam</code></li>" in html
    assert "Rename and save 2 documents" in html
    # The review reads through Inventor (open, close) and writes nothing.
    assert (root / "Frame" / "parts" / "Body.ipt").is_file()
    assert {entry[0] for entry in app.log} == {"open", "close"} and app.ours() == []

    done = client.post("/doctor/name/Body.ipt", data={**form, "confirm_repair": "1"})
    assert done.status_code == 302
    entry = read_ledger(root)[0]
    assert done.headers["Location"].endswith(
        f"/doctor/name/Body.ipt?renamed=1&entry={entry.id}"
    )
    assert entry.settled and entry.fully_repaired

    page = client.get(done.headers["Location"]).get_data(as_text=True)
    assert (
        "Renamed and repaired through Inventor 2027.1: Frame\\probe.iam, Frame\\stand.iam "
        "saved and verified."
    ) in page
    # The saved assemblies still carry Body.ipt as a fossil, but no longer name it.
    assert b"B\x00o\x00d\x00y\x00.\x00i\x00p\x00t" in (root / "Frame" / "probe.iam").read_bytes()
    assert "No assembly, drawing, or presentation currently embeds this filename." in page
    part = client.get("/part/Frame/parts/Frame-body.ipt").get_data(as_text=True)
    assert "Frame\\probe.iam" in part and "Frame\\stand.iam" in part

    ledger = client.get("/renames").get_data(as_text=True)
    assert "Repaired through Inventor." in ledger
    assert f'data-rename-settled="{entry.id}" checked' in ledger
    assert ledger.count('class="referrer-repaired">repaired</small>') == 2
    assert "<dt>Repaired</dt><dd>1</dd>" in ledger


def test_part_rename_through_inventor_names_the_saved_assemblies(tmp_path: Path) -> None:
    root, app = make_workspace(tmp_path)
    session = fake_session(app)
    flask_app = create_app(root, session_factory=lambda: session)
    client = flask_app.test_client()
    form = {"token": flask_app.config["FORM_TOKEN"], "new_name": "Frame-body", "repair": "1"}

    review = client.post("/part/Frame/parts/Body.ipt/rename", data=form)
    assert review.status_code == 409
    assert "Rename and save 2 documents" in review.get_data(as_text=True)

    done = client.post("/part/Frame/parts/Body.ipt/rename", data={**form, "confirm_repair": "1"})
    assert done.status_code == 302
    page = client.get(done.headers["Location"]).get_data(as_text=True)
    assert "Frame\\probe.iam, Frame\\stand.iam saved and verified." in page


def test_the_confirmation_names_a_referrer_that_uses_another_copy(tmp_path: Path) -> None:
    root, app = make_workspace(tmp_path)
    other = root / "Other" / "Body.ipt"
    other.parent.mkdir()
    other.write_bytes(b"other geometry")
    bracket = root / "Other" / "bracket.iam"
    bracket.write_bytes(reference_bytes(str(other)))
    app.disk[str(bracket).casefold()] = [str(other)]
    session = fake_session(app)
    flask_app = create_app(root, session_factory=lambda: session)
    client = flask_app.test_client()
    form = {
        "token": flask_app.config["FORM_TOKEN"],
        "relative_path": "Frame/parts/Body.ipt",
        "new_name": "Frame-body",
        "repair": "1",
    }

    html = client.post("/doctor/name/Body.ipt", data=form).get_data(as_text=True)
    assert "Rename and save 2 documents" in html
    assert "<li><code>Other\\bracket.iam</code>: uses another file with the old name</li>" in html

    client.post("/doctor/name/Body.ipt", data={**form, "confirm_repair": "1", "confirm_collision": "1"})
    entry = read_ledger(root)[0]
    assert entry.repaired == ("Frame/probe.iam", "Frame/stand.iam")
    assert not entry.settled
    assert app.disk[str(bracket).casefold()] == [str(other)]
    assert other.is_file()


def test_rename_only_from_the_confirmation_skips_inventor(tmp_path: Path) -> None:
    root, app = make_workspace(tmp_path)
    session = fake_session(app)
    flask_app = create_app(root, session_factory=lambda: session)
    client = flask_app.test_client()

    done = client.post(
        "/part/Frame/parts/Body.ipt/rename",
        data={"token": flask_app.config["FORM_TOKEN"], "new_name": "Frame-body"},
    )

    assert done.status_code == 302 and "entry=" not in done.headers["Location"]
    assert app.log == []
    entry = read_ledger(root)[0]
    assert entry.repaired == () and not entry.settled


def test_a_repair_asked_for_after_inventor_closed_renames_nothing(tmp_path: Path) -> None:
    root, _ = make_workspace(tmp_path)
    flask_app = create_app(root)
    client = flask_app.test_client()

    response = client.post(
        "/part/Frame/parts/Body.ipt/rename",
        data={
            "token": flask_app.config["FORM_TOKEN"],
            "new_name": "Frame-body",
            "repair": "1",
            "confirm_repair": "1",
        },
    )

    assert response.status_code == 409
    assert "Inventor is not running; nothing was renamed." in response.get_data(as_text=True)
    assert (root / "Frame" / "parts" / "Body.ipt").is_file() and read_ledger(root) == ()


# ---- CLI -------------------------------------------------------------------


def test_cli_rename_dry_prints_the_plan_and_touches_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    root, app = make_workspace(tmp_path)
    monkeypatch.setattr(inventor_session, "connect", lambda **_: fake_session(app))

    code = cli.main(["rename", "Frame/parts/Body.ipt", "Frame-body", str(root), "--repair", "--dry"])

    out = capsys.readouterr().out
    assert code == 0
    assert "inventor: 2027.1" in out
    assert "Frame\\probe.iam: will repoint 1 reference" in out
    assert "DRY RUN: nothing renamed or saved" in out
    assert (root / "Frame" / "parts" / "Body.ipt").is_file() and read_ledger(root) == ()
    assert not any(entry[0] in {"replace", "save"} for entry in app.log)


def test_cli_rename_repair_reports_each_referrer(tmp_path: Path, monkeypatch, capsys) -> None:
    root, app = make_workspace(tmp_path)
    monkeypatch.setattr(inventor_session, "connect", lambda **_: fake_session(app))

    code = cli.main(["rename", "Frame/parts/Body.ipt", "Frame-body", str(root), "--repair"])

    out = capsys.readouterr().out
    assert code == 0
    assert "RENAMED Frame\\parts\\Body.ipt -> Frame\\parts\\Frame-body.ipt" in out
    assert "Frame\\stand.iam: repaired" in out
    assert "settled=yes" in out and "note: repaired through Inventor 2027.1" in out


def test_cli_rename_repair_without_inventor_renames_nothing(tmp_path: Path, capsys) -> None:
    root, _ = make_workspace(tmp_path)

    code = cli.main(["rename", "Frame/parts/Body.ipt", "Frame-body", str(root), "--repair"])

    assert code == 2
    assert "Inventor is not running" in capsys.readouterr().err
    assert (root / "Frame" / "parts" / "Body.ipt").is_file()
