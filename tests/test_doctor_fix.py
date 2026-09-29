"""Doctor's buttons: repoint a missing name, rename a repeated one, through Inventor.

Every session here is the fake from `inventor_fake`; the suite-wide guard in
`conftest.py` keeps `inventor_session.connect` answering None, so no test
reaches a real Inventor.
"""

import json
from pathlib import Path

import pytest
from inventor_fake import FakeDocument, FakeInventor, fake_session, key, reference_bytes

from pihti_dedup import step_mirror
from pihti_dedup.renames import (
    REPOINT_NOTE,
    RenameEntry,
    append_entry,
    check_filename,
    read_ledger,
    record_repoint,
    suggest_unique_name,
)
from pihti_dedup.web import DOCTOR_ABSENT, create_app

CLIP = "Wide Din Clip.ipt"
FOLDERS = {
    "TempController": ("TempController.iam", "Wide Din Clip V1.ipt"),
    "TempController-v2": ("TempController-v2.iam", "Wide Din Clip v2.ipt"),
    "Win-GPIO-Box": ("cosel-psu-din-clip.iam", "Wide Din Clip v3.ipt"),
}


def clip_workspace(root: Path, *, ledger: bool = True) -> tuple[Path, FakeInventor]:
    """The August renames: one clip became three, every assembly still names the old one."""

    root = root.resolve()
    (root / "PIHTI.ipj").write_bytes(b"")
    disk = {}
    referrers = [f"Box/{folder}/{names[0]}" for folder, names in FOLDERS.items()]
    for position, (folder, (assembly, clip)) in enumerate(FOLDERS.items()):
        home = root / "Box" / folder
        home.mkdir(parents=True)
        (home / clip).write_bytes(clip.encode())
        old = str(home / CLIP)
        (home / assembly).write_bytes(reference_bytes(old))
        disk[home / assembly] = [old]
        if ledger:
            append_entry(
                root,
                RenameEntry(
                    id="",
                    timestamp=f"2026-08-06T13:3{position}:00+00:00",
                    old_path=f"Box/{folder}/{CLIP}",
                    new_path=f"Box/{folder}/{clip}",
                    old_name=CLIP,
                    new_name=clip,
                    where_used=tuple(referrers),
                    will_prompt=position == 0,
                ),
            )
    return root, FakeInventor(disk)


def client_for(root: Path, app: FakeInventor | None):
    session = fake_session(app) if app is not None else None
    flask_app = create_app(root, session_factory=lambda: session)
    return flask_app, flask_app.test_client()


def repoint(client, flask_app, referrer: str, target: str, **extra):
    return client.post(
        f"/doctor/name/{CLIP}/repoint",
        data={
            "token": flask_app.config["FORM_TOKEN"],
            "referrer": referrer,
            "target": target,
            **extra,
        },
    )


def by_new_name(root: Path) -> dict[str, RenameEntry]:
    return {entry.new_name: entry for entry in read_ledger(root)}


# ---- missing name: one row per referring assembly -----------------------------


def test_the_missing_name_page_offers_a_file_per_assembly(tmp_path: Path) -> None:
    root, app = clip_workspace(tmp_path)
    _flask_app, client = client_for(root, app)

    html = client.get(f"/doctor/name/{CLIP}").get_data(as_text=True)

    assert "<h2>Missing file</h2>" in html
    assert html.count(">Fix in Inventor</button>") == 3
    assert html.count('name="referrer"') == 3
    # The ledger's successors, each preselected for the assembly beside it.
    row = html.split('value="Box/TempController/TempController.iam"', 1)[1].split("</form>", 1)[0]
    assert '<option value="Box/TempController/Wide Din Clip V1.ipt" selected' in row
    assert '<option value="Box/TempController-v2/Wide Din Clip v2.ipt"' in row
    assert '<option value="Box/Win-GPIO-Box/Wide Din Clip v3.ipt"' in row
    assert "press Skip" not in html  # the owner never acts on a dialog
    # Reading the page opened nothing in Inventor.
    assert [entry for entry in app.log if entry[0] != "open"] == [] and app.ours() == []


def test_fixing_one_assembly_repoints_saves_and_records_it(tmp_path: Path) -> None:
    root, app = clip_workspace(tmp_path)
    flask_app, client = client_for(root, app)
    referrer = "Box/TempController/TempController.iam"
    target = "Box/TempController/Wide Din Clip V1.ipt"

    done = repoint(client, flask_app, referrer, target)

    assert done.status_code == 302
    assert done.headers["Location"].endswith(
        "/doctor/name/Wide%20Din%20Clip.ipt?fixed=Box/TempController/TempController.iam"
    )
    # Inventor opened it without Resolve Link, replaced the one reference,
    # saved without dialogs, closed it, and reopened it the same way to verify.
    actions = [entry[0] for entry in app.log]
    assert actions == ["open-options", "replace", "save", "close", "open-options", "close"]
    assert ("save", "TempController.iam", False) in app.log
    assert app.disk[key(root / referrer)] == [str(root / target)]
    assert app.ours() == []
    # The ledger: repaired in the entry for the chosen file, not applicable in
    # the two others; none settled yet, two assemblies still name the old file.
    entries = by_new_name(root)
    assert entries["Wide Din Clip V1.ipt"].repaired == (referrer,)
    assert entries["Wide Din Clip V1.ipt"].repair_note == "repaired through Inventor 2027.1"
    for name in ("Wide Din Clip v2.ipt", "Wide Din Clip v3.ipt"):
        assert entries[name].not_applicable == (referrer,)
    assert not any(entry.settled for entry in entries.values())
    # The row stays for this view with its result; the others still offer the fix.
    page = client.get(done.headers["Location"]).get_data(as_text=True)
    assert "TempController.iam: repaired → Wide Din Clip V1.ipt" in page
    assert '<span class="fix-result is-done">repaired → Wide Din Clip V1.ipt</span>' in page
    assert page.count(">Fix in Inventor</button>") == 2


def test_the_ledger_settles_when_the_last_assembly_is_fixed(tmp_path: Path) -> None:
    root, app = clip_workspace(tmp_path)
    flask_app, client = client_for(root, app)
    assert step_mirror.renamed_names(read_ledger(root)) == frozenset({CLIP.casefold()})
    assert "<h2>Missing file</h2>" in client.get("/doctor").get_data(as_text=True)

    for folder, (assembly, clip) in FOLDERS.items():
        response = repoint(client, flask_app, f"Box/{folder}/{assembly}", f"Box/{folder}/{clip}")
        assert response.status_code == 302

    entries = read_ledger(root)
    assert len(entries) == 3
    for entry in entries:
        assert entry.settled and entry.fully_repaired and entry.will_prompt is False
        assert len(entry.repaired) == 1 and len(entry.not_applicable) == 2
    # Nothing names the old file any more: off the queue, and off the
    # mirror's needs-Doctor rule.
    assert step_mirror.renamed_names(entries) == frozenset()
    queue = client.get("/doctor").get_data(as_text=True)
    assert 'id="missing"' not in queue
    page = client.get(f"/doctor/name/{CLIP}").get_data(as_text=True)
    assert f"No assembly names {CLIP}" in page
    ledger = client.get("/renames").get_data(as_text=True)
    assert ledger.count('class="referrer-repaired">repaired</small>') == 3


def test_a_missing_name_the_ledger_never_renamed_gets_its_own_line(tmp_path: Path) -> None:
    root, app = clip_workspace(tmp_path, ledger=False)
    flask_app, client = client_for(root, app)
    referrer = "Box/Win-GPIO-Box/cosel-psu-din-clip.iam"
    target = "Box/Win-GPIO-Box/Wide Din Clip v3.ipt"
    html = client.get(f"/doctor/name/{CLIP}").get_data(as_text=True)
    # No ledger: the candidates are the files whose stem starts with the old stem.
    assert html.count('<option value="Box/Win-GPIO-Box/Wide Din Clip v3.ipt"') == 3

    assert repoint(client, flask_app, referrer, target).status_code == 302

    (entry,) = read_ledger(root)
    assert entry.old_name == CLIP and entry.new_path == target
    assert entry.old_path == f"Box/Win-GPIO-Box/{CLIP}"
    assert entry.where_used == (referrer,) and entry.repaired == (referrer,)
    assert entry.settled and entry.will_prompt is False and entry.notes == REPOINT_NOTE
    assert (root / target).is_file()  # nothing was renamed


def test_a_missing_name_is_opened_only_with_skip_all_unresolved_files(tmp_path: Path) -> None:
    root, app = clip_workspace(tmp_path)
    flask_app, client = client_for(root, app)

    response = repoint(
        client, flask_app, "Box/TempController/TempController.iam",
        "Box/TempController/Wide Din Clip V1.ipt",
    )

    assert response.status_code == 302
    opens = [entry for entry in app.log if entry[0].startswith("open")]
    assert opens == [
        ("open-options", "TempController.iam", {"SkipAllUnresolvedFiles": True}, False),
        ("open-options", "TempController.iam", {"SkipAllUnresolvedFiles": True}, False),
    ]
    # Plain Open, which would raise Resolve Link, is never called here.
    assert not any(entry[0] == "open" for entry in app.log)


def test_a_session_without_the_dialog_free_open_says_inventor_would_ask(tmp_path: Path) -> None:
    root, app = clip_workspace(tmp_path)
    app.legacy_api = True
    flask_app, client = client_for(root, app)
    assembly = root / "Box" / "TempController" / "TempController.iam"
    before = assembly.read_bytes()

    refused = repoint(
        client, flask_app, "Box/TempController/TempController.iam",
        "Box/TempController/Wide Din Clip V1.ipt",
    )

    assert refused.status_code == 409
    assert '<p class="fix-result is-failed" role="alert">Inventor would ask</p>' in (
        refused.get_data(as_text=True)
    )
    assert app.log == []  # nothing opened, nothing saved, no plain Open fallback
    assert assembly.read_bytes() == before
    assert not any(entry.repaired or entry.not_applicable for entry in read_ledger(root))


def test_without_inventor_the_fix_changes_nothing_and_says_so(tmp_path: Path) -> None:
    root, app = clip_workspace(tmp_path)
    flask_app, client = client_for(root, None)
    before = (root / ".agents" / "rename-ledger.jsonl").read_bytes()
    assembly = root / "Box" / "TempController" / "TempController.iam"
    bytes_before = assembly.read_bytes()

    page = client.get(f"/doctor/name/{CLIP}").get_data(as_text=True)
    assert ">Fix in Inventor</button>" not in page
    assert page.count('<span class="queue-count session-absent">Start Inventor</span>') == 3
    assert "Start Inventor, open PIHTI.ipj, then come back" in page

    refused = repoint(
        client, flask_app, "Box/TempController/TempController.iam",
        "Box/TempController/Wide Din Clip V1.ipt",
    )
    assert refused.status_code == 409
    assert DOCTOR_ABSENT in refused.get_data(as_text=True)
    assert (root / ".agents" / "rename-ledger.jsonl").read_bytes() == before
    assert assembly.read_bytes() == bytes_before
    assert app.log == []


def test_an_assembly_open_in_inventor_is_never_touched(tmp_path: Path) -> None:
    root, app = clip_workspace(tmp_path)
    referrer = root / "Box" / "TempController" / "TempController.iam"
    app.loaded.append(FakeDocument(app, str(referrer), owner=True))
    flask_app, client = client_for(root, app)

    refused = repoint(
        client, flask_app, "Box/TempController/TempController.iam",
        "Box/TempController/Wide Din Clip V1.ipt",
    )

    assert refused.status_code == 409
    assert "TempController.iam is open in Inventor: close it first; nothing changed" in (
        refused.get_data(as_text=True)
    )
    assert app.violations == [] and not any(entry.repaired for entry in read_ledger(root))


def test_a_failed_save_shows_on_the_row_and_records_nothing(tmp_path: Path) -> None:
    root, app = clip_workspace(tmp_path)
    referrer = root / "Box" / "TempController" / "TempController.iam"
    app.fail_save.add(key(referrer))
    flask_app, client = client_for(root, app)

    refused = repoint(
        client, flask_app, "Box/TempController/TempController.iam",
        "Box/TempController/Wide Din Clip V1.ipt",
    )

    html = refused.get_data(as_text=True)
    assert refused.status_code == 409
    assert '<p class="fix-result is-failed" role="alert">the file is read-only</p>' in html
    assert not any(entry.repaired or entry.not_applicable for entry in read_ledger(root))
    assert app.ours() == []


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        ("", "choose the file to point it at"),
        ("Box/TempController/TempController.iam", "TempController.iam is not a .ipt file"),
        ("Box/../outside.ipt", "choose the file to point it at"),
    ],
)
def test_the_fix_refuses_a_target_it_cannot_use(tmp_path: Path, target: str, reason: str) -> None:
    root, app = clip_workspace(tmp_path)
    flask_app, client = client_for(root, app)

    refused = repoint(client, flask_app, "Box/TempController/TempController.iam", target)

    assert refused.status_code == 409 and reason in refused.get_data(as_text=True)
    assert app.log == []


def test_the_fix_refuses_when_the_old_name_exists_again_or_is_no_longer_named(
    tmp_path: Path,
) -> None:
    root, app = clip_workspace(tmp_path)
    flask_app, client = client_for(root, app)
    target = "Box/TempController/Wide Din Clip V1.ipt"

    (root / "Box" / "TempController" / CLIP).write_bytes(b"back")
    again = repoint(client, flask_app, "Box/TempController/TempController.iam", target)
    assert again.status_code == 409 and f"{CLIP} exists again; nothing changed" in again.get_data(
        as_text=True
    )
    (root / "Box" / "TempController" / CLIP).unlink()

    (root / "Box" / "TempController" / "TempController.iam").write_bytes(reference_bytes("x.ipt"))
    gone = repoint(client, flask_app, "Box/TempController/TempController.iam", target)
    assert gone.status_code == 409
    assert f"TempController.iam no longer names {CLIP}" in gone.get_data(as_text=True)
    assert app.log == []


def test_the_fix_needs_the_token_and_localhost(tmp_path: Path) -> None:
    root, app = clip_workspace(tmp_path)
    flask_app, client = client_for(root, app)
    data = {
        "referrer": "Box/TempController/TempController.iam",
        "target": "Box/TempController/Wide Din Clip V1.ipt",
    }

    assert client.post(f"/doctor/name/{CLIP}/repoint", data=data).status_code == 403
    remote = client.post(
        f"/doctor/name/{CLIP}/repoint",
        data={**data, "token": flask_app.config["FORM_TOKEN"]},
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    )
    assert remote.status_code == 403
    assert app.log == []


def test_the_queue_fixes_in_place_when_there_is_one_obvious_file(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / "PIHTI.ipj").write_bytes(b"")
    home = root / "Frame"
    home.mkdir()
    (home / "Bracket v2.ipt").write_bytes(b"new")
    old = str(home / "Bracket.ipt")
    (home / "frame.iam").write_bytes(reference_bytes(old))
    append_entry(
        root,
        RenameEntry(
            id="", timestamp="2026-09-01T00:00:00+00:00", old_path="Frame/Bracket.ipt",
            new_path="Frame/Bracket v2.ipt", old_name="Bracket.ipt", new_name="Bracket v2.ipt",
            where_used=("Frame/frame.iam",),
        ),
    )
    app = FakeInventor({home / "frame.iam": [old]})
    flask_app, client = client_for(root, app)

    queue = client.get("/doctor").get_data(as_text=True)
    missing = queue.split('id="missing"', 1)[1].split("</section>", 1)[0]
    assert '<a href="/doctor/name/Bracket.ipt">Bracket.ipt</a>' in missing
    assert '<span class="queue-count">1 assembly</span>' in missing
    assert '<input type="hidden" name="origin" value="doctor">' in missing
    assert ">Fix in Inventor</button>" in missing
    # Without a session the same line opens the item page instead.
    _flask, absent = client_for(root, None)
    absent_missing = absent.get("/doctor").get_data(as_text=True).split('id="missing"', 1)[1]
    absent_missing = absent_missing.split("</section>", 1)[0]
    assert ">Fix in Inventor</button>" not in absent_missing
    assert '<a class="copy-path" href="/doctor/name/Bracket.ipt">Open</a>' in absent_missing

    done = client.post(
        "/doctor/name/Bracket.ipt/repoint",
        data={
            "token": flask_app.config["FORM_TOKEN"],
            "referrer": "Frame/frame.iam",
            "target": "Frame/Bracket v2.ipt",
            "origin": "doctor",
        },
    )
    assert done.status_code == 302
    after = client.get(done.headers["Location"]).get_data(as_text=True)
    assert "frame.iam: repaired → Bracket v2.ipt" in after
    assert 'id="missing"' not in after
    (entry,) = read_ledger(root)
    assert entry.settled and entry.repaired == ("Frame/frame.iam",)


def test_the_assembly_page_fixes_its_own_missing_name(tmp_path: Path) -> None:
    root, app = clip_workspace(tmp_path)
    flask_app, client = client_for(root, app)
    assembly = "Box/TempController-v2/TempController-v2.iam"

    page = client.get(f"/doctor/assembly/{assembly}").get_data(as_text=True)
    assert page.count(">Fix in Inventor</button>") == 1
    assert '<input type="hidden" name="origin" value="assembly">' in page
    assert '<option value="Box/TempController-v2/Wide Din Clip v2.ipt" selected' in page

    done = repoint(
        client, flask_app, assembly, "Box/TempController-v2/Wide Din Clip v2.ipt",
        origin="assembly", assembly=assembly,
    )
    assert done.status_code == 302
    assert "/doctor/assembly/Box/TempController-v2/TempController-v2.iam?fixed=" in done.headers[
        "Location"
    ]
    after = client.get(done.headers["Location"]).get_data(as_text=True)
    assert "Wide Din Clip.ipt: repaired → Wide Din Clip v2.ipt" in after
    assert ">Fix in Inventor</button>" not in after


def test_the_assemblies_queue_lists_only_actual_problems(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / "PIHTI.ipj").write_bytes(b"")
    home = root / "Frame"
    home.mkdir()
    (home / "plate.ipt").write_bytes(b"plate")
    # A fossil: the template name the byte scan finds in every assembly.
    (home / "fossil.iam").write_bytes(reference_bytes("Standard (mm).iam", str(home / "plate.ipt")))
    (home / "renamed.iam").write_bytes(reference_bytes(str(home / "Bracket.ipt")))
    append_entry(
        root,
        RenameEntry(
            id="", timestamp="2026-09-01T00:00:00+00:00", old_path="Frame/Bracket.ipt",
            new_path="Frame/plate.ipt", old_name="Bracket.ipt", new_name="plate.ipt",
            where_used=("Frame/renamed.iam",),
        ),
    )
    _flask, client = client_for(root, None)

    queue = client.get("/doctor").get_data(as_text=True)
    section = queue.split('id="assemblies"', 1)[1].split("</section>", 1)[0]
    assert 'href="/doctor/assembly/Frame/renamed.iam"' in section
    assert '<span class="queue-count">1 missing</span>' in section
    assert "fossil.iam" not in section
    # The assembly's own page still shows the fossil with its Git evidence.
    assert client.get("/doctor/assembly/Frame/fossil.iam").status_code == 200


# ---- name carried twice: rename one copy and fix through Inventor -------------


def rkc_workspace(root: Path) -> tuple[Path, FakeInventor]:
    root = root.resolve()
    (root / "PIHTI.ipj").write_bytes(b"")
    disk = {}
    for folder in ("TempController", "TempController-v2"):
        home = root / "Box" / folder
        home.mkdir(parents=True)
        part = home / "RKC CONTROLLER.ipt"
        part.write_bytes(folder.encode())
        (home / f"{folder}.iam").write_bytes(reference_bytes(str(part)))
        disk[home / f"{folder}.iam"] = [str(part)]
    return root, FakeInventor(disk)


def test_each_copy_gets_a_suggested_unique_name(tmp_path: Path) -> None:
    root, app = rkc_workspace(tmp_path)
    _flask_app, client = client_for(root, app)

    html = client.get("/doctor/name/RKC%20CONTROLLER.ipt").get_data(as_text=True)

    assert html.count("data-copy-row") == 2
    assert 'value="RKC CONTROLLER Temp"' in html
    assert 'value="RKC CONTROLLER v2"' in html
    assert html.count(">Rename and fix in Inventor</button>") == 2
    assert html.count("2 assemblies reference this filename") == 2
    assert html.count("Rename this file") == 2


def test_rename_and_fix_round_trip(tmp_path: Path) -> None:
    root, app = rkc_workspace(tmp_path)
    flask_app, client = client_for(root, app)
    url = "/doctor/name/RKC%20CONTROLLER.ipt"
    form = {
        "token": flask_app.config["FORM_TOKEN"],
        "relative_path": "Box/TempController-v2/RKC CONTROLLER.ipt",
        "new_name": "RKC CONTROLLER v2",
        "repair": "1",
    }

    review = client.post(url, data=form)
    html = review.get_data(as_text=True)
    assert review.status_code == 409
    assert "Rename to RKC CONTROLLER v2.ipt · fix in Inventor 2027.1" in html
    assert "Inventor opens, repoints, and saves 1 document:" in html
    assert "<li><code>Box\\TempController-v2\\TempController-v2.iam</code></li>" in html
    assert "Box\\TempController\\TempController.iam</code>: uses another file with the old name" in html
    assert (root / "Box" / "TempController-v2" / "RKC CONTROLLER.ipt").is_file()

    done = client.post(url, data={**form, "confirm_repair": "1", "confirm_collision": "1"})
    assert done.status_code == 302
    (entry,) = read_ledger(root)
    assert entry.new_path == "Box/TempController-v2/RKC CONTROLLER v2.ipt"
    assert entry.repaired == ("Box/TempController-v2/TempController-v2.iam",)
    assert entry.not_applicable == ("Box/TempController/TempController.iam",)
    assert entry.settled and entry.will_prompt is False
    assert (root / "Box" / "TempController-v2" / "RKC CONTROLLER v2.ipt").is_file()
    assert (root / "Box" / "TempController" / "RKC CONTROLLER.ipt").is_file()
    page = client.get(done.headers["Location"]).get_data(as_text=True)
    assert "Renamed and repaired through Inventor 2027.1" in page


def test_a_suggested_name_that_exists_is_refused_by_the_collision_guard(tmp_path: Path) -> None:
    root, app = rkc_workspace(tmp_path)
    (root / "Box" / "RKC CONTROLLER v2.ipt").write_bytes(b"already here")
    flask_app, client = client_for(root, app)

    html = client.get("/doctor/name/RKC%20CONTROLLER.ipt").get_data(as_text=True)
    # The page never suggests a name the workspace already carries.
    assert 'value="RKC CONTROLLER v2"' not in html

    refused = client.post(
        "/doctor/name/RKC%20CONTROLLER.ipt",
        data={
            "token": flask_app.config["FORM_TOKEN"],
            "relative_path": "Box/TempController-v2/RKC CONTROLLER.ipt",
            "new_name": "RKC CONTROLLER v2",
            "repair": "1",
        },
    )
    assert refused.status_code == 400
    assert "already exists in the workspace" in refused.get_data(as_text=True)
    assert app.log == [] and read_ledger(root) == ()


# ---- the pure pieces ------------------------------------------------------------


def test_suggested_names_read_the_nearest_folder_that_says_something() -> None:
    assert suggest_unique_name("Box/TempController/RKC CONTROLLER.ipt", {}) == (
        "RKC CONTROLLER Temp.ipt"
    )
    assert suggest_unique_name("Box/TempController-v2/RKC CONTROLLER.ipt", {}) == (
        "RKC CONTROLLER v2.ipt"
    )
    # "STEPs" and "parts" say nothing; the next folder up does.
    assert suggest_unique_name("Box/GX12 connector/STEPs/Body001.ipt", {}) == (
        "Body001 GX12 connector.ipt"
    )
    assert suggest_unique_name("Plasma Vessel_2026/parts/bearing.ipt", {}) == (
        "bearing Plasma Vessel.ipt"
    )
    # Short: at most a few words of the folder.
    hint = suggest_unique_name("A Very Long Folder Name Here/board.ipt", {})
    assert len(hint) <= len("board ") + 16 + len(".ipt")


def test_suggested_names_never_collide() -> None:
    taken = {"rkc controller v2.ipt": ("Elsewhere/RKC CONTROLLER v2.ipt",)}
    assert suggest_unique_name("Box/TempController-v2/RKC CONTROLLER.ipt", taken) == (
        "RKC CONTROLLER Box.ipt"
    )
    first = suggest_unique_name("A/Body.ipt", {})
    assert suggest_unique_name("B/A/Body.ipt", {}, frozenset({first.casefold()})) == "Body B.ipt"
    assert suggest_unique_name("Body.ipt", {"body 2.ipt": ("x",)}) == "Body 3.ipt"
    for name in (first, "RKC CONTROLLER Temp.ipt"):
        check_filename(name)


def test_record_repoint_keeps_other_entries_open_until_their_last_referrer(tmp_path: Path) -> None:
    root, _app = clip_workspace(tmp_path)
    referrers = [f"Box/{folder}/{names[0]}" for folder, names in FOLDERS.items()]

    entry = record_repoint(
        root, referrer=referrers[0], old_name=CLIP,
        new_path="Box/TempController/Wide Din Clip V1.ipt", version="2027.1",
    )
    assert entry.repaired == (referrers[0],) and not entry.settled
    # Recording the same fix again changes nothing.
    again = record_repoint(
        root, referrer=referrers[0], old_name=CLIP,
        new_path="Box/TempController/Wide Din Clip V1.ipt", version="2027.1",
    )
    assert again.repaired == (referrers[0],)
    lines = (root / ".agents" / "rename-ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3 and all(json.loads(line)["id"] for line in lines)
