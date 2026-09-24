import json
import re
from pathlib import Path

import pytest

import pihti_dedup.cli as cli
import pihti_dedup.web as web
from pihti_dedup.cleanup import read_quarantine_manifests
from pihti_dedup.inventor_meta import DocumentMeta
from pihti_dedup.renames import read_ledger
from pihti_dedup.standard_parts import (
    CONFLICT,
    IDENTICAL,
    MOVE,
    MOVE_NOTE_PREFIX,
    REFUSED,
    StandardMoveError,
    execute_standard_move,
    is_standard_candidate,
    plan_standard_move,
)
from pihti_dedup.web import create_app
from pihti_dedup.whereused import build_index, filename_locations

LIBRARY = Path("ContentCenter") / "Fastners"


def assembly_bytes(*stored_paths: str) -> bytes:
    payload = bytearray(b"\xde\xad" * 4)
    for stored in stored_paths:
        payload += b"\x00\x00" + stored.encode("utf-16-le") + b"\x00\x00"
    return bytes(payload)


def write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def make_standard_workspace(root: Path) -> Path:
    """One movable screw, one copy already in the library, one name collision,
    and the custom look-alikes that must never be proposed."""

    write(root / LIBRARY / "M3-nut.ipt", b"library nut")
    write(root / "Probe" / "parts" / "M3x10-SHCS.ipt", b"cap screw")
    write(root / "Probe" / "parts" / "M3-nut.ipt", b"library nut")
    write(root / "Probe" / "parts" / "anode-holding-nut.ipt", b"custom nut")
    write(root / "Probe" / "bnc-nut-holder.iam", assembly_bytes("parts\\M3-nut.ipt"))
    write(root / "Vessel" / "M4-nut.ipt", b"vessel nut")
    write(root / "Stand" / "M4-nut.ipt", b"stand nut")
    write(
        root / "Probe" / "probe.iam",
        assembly_bytes("parts\\M3x10-SHCS.ipt", "parts\\anode-holding-nut.ipt"),
    )
    return root


def tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".pihti-dedup" not in path.parts
    }


def plan_for(root: Path, relative: str, **kwargs):
    return plan_standard_move(
        root,
        relative,
        index=build_index(root),
        locations=filename_locations(root),
        **kwargs,
    )


# --- evidence ---------------------------------------------------------------


def test_each_evidence_class_is_named_in_the_result() -> None:
    iproperty = is_standard_candidate("bellows/odd-name.ipt", {"standard": "JIS B 1176"})
    assert iproperty.kinds == ("iproperty",)
    assert iproperty.labels == ("iProperty standard: JIS B 1176",)

    din = is_standard_candidate(
        "LIBS/XL430/countersunk screw_din_DIN EN ISO 7046-1 - M2.5 x 10 - Z.ipt", {}
    )
    assert din.kinds == ("name",)
    assert din.labels == ("name: DIN EN ISO 7046-1",)
    assert is_standard_candidate("x/ANSI B18.3.4M - M3 x 6.ipt", None).labels == (
        "name: ANSI B18.3.4M",
    )
    assert is_standard_candidate("x/JIS B 1176 - M3 x 16 - 0.5.ipt", None).labels == (
        "name: JIS B 1176",
    )

    for name in ("M3x10-SHCS.ipt", "M2.5x10-SHCS.ipt", "M4-Washer.ipt", "M6-nut-WA5.ipt",
                 "M4x12-Fillips-Countersink.ipt", "M3x5-set-screw.ipt"):
        found = is_standard_candidate(f"Probe/parts/{name}", {})
        assert found is not None and found.kinds == ("convention",), name
        assert found.labels == ("Fastners convention",)

    described = is_standard_candidate("Probe/bolt17.ipt", {"description": "六角穴付きボルト"})
    assert described.kinds == ("description",)
    assert described.labels == ("description",)

    everything = is_standard_candidate(
        "BoronProbe_2026/parts/M3x10-BHCS.ipt",
        {
            "standard": "ANSI B18.3.4M",
            "description": "Broached Hexagon Socket Button Head Cap Screw - Metric",
        },
    )
    assert everything.kinds == ("iproperty", "convention", "description")


def test_custom_look_alikes_and_excluded_folders_are_not_candidates() -> None:
    for path in (
        "ElectronicsBox/LP-box/bnc-nut-holder.iam",
        "Plasma Vessel/Cathode-Anode-Flange/anode-holding-nut.ipt",
        "PALP/Oring-seal/Oring_M48-2_nut.ipt",
        "PLD/m4x60-pin.ipt",
        "ElectronicsBox/firstki/R_Axial_DIN0617_L170mm_D60mm_P2032mm_Horizontal.ipt",
        "ContentCenter/Fastners/M3-nut.ipt",
        "ElectronicsBox/TempController-v2/STEPs/Socket/M3x10-SHCS.ipt",
        "Probe/OldVersions/M3x10-SHCS.ipt",
        "Probe/M3x10-SHCS.stp",
    ):
        assert is_standard_candidate(path, {}) is None, path
    # An assembly is never proposed, whatever its iProperties say.
    assert is_standard_candidate("Probe/bolts.iam", {"standard": "ISO 4762"}) is None


# --- plans ------------------------------------------------------------------


def test_plan_outcomes_for_unique_identical_and_colliding_names(tmp_path: Path) -> None:
    root = make_standard_workspace(tmp_path)

    unique = plan_for(root, "Probe/parts/M3x10-SHCS.ipt")
    assert unique.outcome == MOVE
    assert unique.destination_path == "ContentCenter/Fastners/M3x10-SHCS.ipt"
    assert unique.referrers == ("Probe/probe.iam",)
    assert unique.will_prompt is False

    identical = plan_for(root, "Probe/parts/M3-nut.ipt")
    assert identical.outcome == IDENTICAL
    assert identical.survivor_path == "ContentCenter/Fastners/M3-nut.ipt"
    assert identical.referrers == ("Probe/bnc-nut-holder.iam",)

    collision = plan_for(root, "Vessel/M4-nut.ipt")
    assert collision.outcome == CONFLICT
    assert collision.other_locations == ("Stand/M4-nut.ipt",)
    assert "Stand/M4-nut.ipt" in collision.reason

    write(root / LIBRARY / "M3x10-SHCS.ipt", b"another revision")
    different = plan_for(root, "Probe/parts/M3x10-SHCS.ipt")
    assert different.outcome == CONFLICT
    assert "different bytes" in different.reason


def test_a_path_past_the_length_limit_is_refused(tmp_path: Path) -> None:
    (tmp_path / LIBRARY).mkdir(parents=True)
    folder = tmp_path / "p"
    folder.mkdir()
    room = 250 - len(str(folder)) - 1
    if room < 30:
        pytest.skip("the temporary root is too deep to build a near-limit path")
    name = "M3x10-SHCS " + "x" * (room - len("M3x10-SHCS .ipt")) + ".ipt"
    write(folder / name, b"screw")

    plan = plan_for(tmp_path, f"p/{name}")

    assert plan.outcome == REFUSED
    assert "260" in plan.reason


# --- execution --------------------------------------------------------------


def test_execute_moves_the_file_and_sidecar_and_ledgers_a_silent_rebind(tmp_path: Path) -> None:
    root = make_standard_workspace(tmp_path)
    source = root / "Probe" / "parts" / "M3x10-SHCS.ipt"
    companion = write(root / "Probe" / "parts" / "M3x10-SHCS.ipt.md", b"---\nstatus: draft\n---\n")
    plan = plan_for(root, "Probe/parts/M3x10-SHCS.ipt", evidence=("Fastners convention",))

    with pytest.raises(StandardMoveError):
        execute_standard_move(root, plan, confirmed=False)
    assert source.is_file()

    result = execute_standard_move(root, plan, confirmed=True)

    assert not source.exists() and not companion.exists()
    assert (root / LIBRARY / "M3x10-SHCS.ipt").read_bytes() == b"cap screw"
    assert (root / LIBRARY / "M3x10-SHCS.ipt.md").is_file()
    assert result.sidecar_moved is True
    entries = read_ledger(root)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.id == result.entry.id
    assert entry.old_path == "Probe/parts/M3x10-SHCS.ipt"
    assert entry.new_path == "ContentCenter/Fastners/M3x10-SHCS.ipt"
    assert entry.old_name == entry.new_name == "M3x10-SHCS.ipt"
    assert entry.will_prompt is False
    assert entry.where_used == ("Probe/probe.iam",)
    assert entry.notes.startswith(MOVE_NOTE_PREFIX)
    assert "Fastners convention" in entry.notes
    assert entry.is_move is True

    page = create_app(root).test_client().get("/renames").get_data(as_text=True)
    assert "Moved; Inventor finds it by filename." in page
    assert "Inventor will NOT ask now." not in page
    assert f'data-copy-text="{root / LIBRARY / "M3x10-SHCS.ipt"}"' in page
    assert "Probe\\parts\\M3x10-SHCS.ipt" in page


def test_execute_revalidates_bytes_and_the_collision_map(tmp_path: Path) -> None:
    root = make_standard_workspace(tmp_path)
    plan = plan_for(root, "Probe/parts/M3x10-SHCS.ipt")

    write(root / "Elsewhere" / "M3x10-SHCS.ipt", b"a late copy")
    with pytest.raises(StandardMoveError, match="changed since review"):
        execute_standard_move(root, plan, confirmed=True)
    (root / "Elsewhere" / "M3x10-SHCS.ipt").unlink()

    (root / "Probe" / "parts" / "M3x10-SHCS.ipt").write_bytes(b"resaved screw")
    with pytest.raises(StandardMoveError, match="changed after review"):
        execute_standard_move(root, plan, confirmed=True)

    with pytest.raises(StandardMoveError):
        execute_standard_move(root, plan_for(root, "Vessel/M4-nut.ipt"), confirmed=True)
    assert (root / "Probe" / "parts" / "M3x10-SHCS.ipt").is_file()
    assert read_ledger(root) == ()


def test_an_identical_library_copy_quarantines_the_stray_and_keeps_the_survivor(
    tmp_path: Path,
) -> None:
    root = make_standard_workspace(tmp_path)
    plan = plan_for(root, "Probe/parts/M3-nut.ipt")

    result = execute_standard_move(root, plan, confirmed=True)

    assert not (root / "Probe" / "parts" / "M3-nut.ipt").exists()
    assert (root / LIBRARY / "M3-nut.ipt").read_bytes() == b"library nut"
    assert result.entry is None
    assert read_ledger(root) == ()
    manifest = json.loads(Path(result.quarantine.manifest).read_text(encoding="utf-8"))
    assert manifest["source"] == "standard-part"
    assert manifest["keep_path"] == "ContentCenter/Fastners/M3-nut.ipt"
    assert manifest["files"][0]["path"] == "Probe/parts/M3-nut.ipt"


# --- CLI --------------------------------------------------------------------


def test_cli_dry_run_prints_the_table_and_writes_nothing(tmp_path: Path, capsys) -> None:
    root = make_standard_workspace(tmp_path)
    before = tree(root)

    assert cli.main(["standard-parts", str(root), "--dry"]) == 0

    output = capsys.readouterr().out
    assert "standard-part candidates: 4" in output
    assert re.search(r"MOVE\s+Probe\\parts\\M3x10-SHCS\.ipt", output)
    assert re.search(r"ALREADY-THERE-IDENTICAL\s+Probe\\parts\\M3-nut\.ipt", output)
    assert re.search(r"CONFLICT\s+Stand\\M4-nut\.ipt", output)
    assert "destination: ContentCenter\\Fastners\\M3x10-SHCS.ipt" in output
    assert "evidence: Fastners convention" in output
    assert "anode-holding-nut" not in output
    assert "bnc-nut-holder" not in output
    assert "DRY RUN" in output
    assert tree(root) == before
    assert not (tmp_path.parent / f"{tmp_path.name}-quarantine").exists()


def test_cli_apply_moves_only_plain_moves_and_prints_ledger_ids(tmp_path: Path, capsys) -> None:
    root = make_standard_workspace(tmp_path)
    before = tree(root)

    assert cli.main(["standard-parts", str(root), "--apply"]) == 2
    assert tree(root) == before
    capsys.readouterr()

    assert cli.main(["standard-parts", str(root), "--apply", "--references-checked"]) == 0

    output = capsys.readouterr().out
    entry = read_ledger(root)[0]
    assert f"(ledger {entry.id})" in output
    assert (root / LIBRARY / "M3x10-SHCS.ipt").is_file()
    # The identical copy and the collision are never touched in bulk.
    assert (root / "Probe" / "parts" / "M3-nut.ipt").is_file()
    assert (root / "Vessel" / "M4-nut.ipt").is_file()
    assert len(read_ledger(root)) == 1


# --- web --------------------------------------------------------------------


def test_doctor_shows_the_standard_parts_card_with_its_count(tmp_path: Path) -> None:
    client = create_app(make_standard_workspace(tmp_path)).test_client()

    html = client.get("/doctor").get_data(as_text=True)

    assert "<h2>Standard parts</h2>" in html
    assert 'href="/doctor/standard-parts"' in html
    assert "4 standard parts outside the library" in html
    assert "1 ready to move · 3 need a decision first" in html


def test_standard_parts_page_groups_rows_by_outcome(tmp_path: Path, monkeypatch) -> None:
    root = make_standard_workspace(tmp_path)
    monkeypatch.setattr(
        web,
        "read_inventor_document",
        lambda path: DocumentMeta(
            path=str(path),
            ok=True,
            fields={"standard": "JIS B 1181"} if path.name == "M3-nut.ipt" else {},
        ),
    )
    client = create_app(root).test_client()

    response = client.get("/doctor/standard-parts")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert html.index('id="sec-move"') < html.index('id="sec-already-there-identical"')
    assert html.index('id="sec-already-there-identical"') < html.index('id="sec-conflict"')
    assert html.count("data-standard-row ") == 4
    assert "iProperty standard: JIS B 1181" in html
    assert "Fastners convention" in html
    assert ">Move</button>" in html
    assert ">Quarantine copy</button>" in html
    assert "Surviving copy" in html and "ContentCenter\\Fastners\\M3-nut.ipt" in html
    assert 'href="/doctor/name/M4-nut.ipt"' in html and "Open in Collision Doctor" in html
    assert html.count("data-standard-skip aria-pressed") == 4
    assert "anode-holding-nut" not in html
    assert "bnc-nut-holder" not in html
    assert "Move all" not in html
    assert 'class="is-current" aria-current="page">Doctor<' in html
    sources = re.findall(r'src="(/preview/[^"]*)"', html)
    assert sources and all(re.search(r"\?v=[0-9a-f]+-[0-9a-f]+-r\d+$", src) for src in sources)


def _row_signature(html: str, path: str) -> str:
    match = re.search(
        r'name="path" value="' + re.escape(path) + r'">\s*<input type="hidden" '
        r'name="signature" value="([0-9a-f]{64})"',
        html,
    )
    assert match, path
    return match.group(1)


def test_move_post_needs_the_token_and_then_moves_and_redirects(tmp_path: Path) -> None:
    root = make_standard_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    html = client.get("/doctor/standard-parts").get_data(as_text=True)
    form = {
        "path": "Probe/parts/M3x10-SHCS.ipt",
        "signature": _row_signature(html, "Probe/parts/M3x10-SHCS.ipt"),
        "confirmed": "1",
    }
    source = root / "Probe" / "parts" / "M3x10-SHCS.ipt"

    assert client.post("/doctor/standard-parts/move", data=form).status_code == 403
    assert client.post(
        "/doctor/standard-parts/move", data={**form, "token": "guessed"}
    ).status_code == 403
    assert client.post(
        "/doctor/standard-parts/move",
        data={**form, "token": app.config["FORM_TOKEN"]},
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    ).status_code == 403
    stale = client.post(
        "/doctor/standard-parts/move",
        data={**form, "token": app.config["FORM_TOKEN"], "signature": "0" * 64},
    )
    assert stale.status_code == 409
    assert "changed since this page was drawn" in stale.get_data(as_text=True)
    assert source.is_file()

    moved = client.post(
        "/doctor/standard-parts/move", data={**form, "token": app.config["FORM_TOKEN"]}
    )

    entry = read_ledger(root)[0]
    assert moved.status_code == 302
    assert moved.headers["Location"].endswith(f"/doctor/standard-parts?moved={entry.id}")
    assert not source.exists()
    assert (root / LIBRARY / "M3x10-SHCS.ipt").is_file()
    after = client.get(moved.headers["Location"]).get_data(as_text=True)
    assert "data-operation-toast" in after
    assert f"Ledger entry {entry.id}" in after
    assert 'data-path="Probe/parts/M3x10-SHCS.ipt"' not in after
    assert "Moved; Inventor finds it by filename." in client.get("/renames").get_data(
        as_text=True
    )


def test_a_move_is_refused_for_a_collision_even_with_a_valid_token(tmp_path: Path) -> None:
    root = make_standard_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    html = client.get("/doctor/standard-parts").get_data(as_text=True)
    assert 'name="path" value="Vessel/M4-nut.ipt"' not in html  # no form for a conflict row

    plan = plan_standard_move(
        root, "Vessel/M4-nut.ipt", index=build_index(root), locations=filename_locations(root)
    )
    refused = client.post(
        "/doctor/standard-parts/move",
        data={
            "token": app.config["FORM_TOKEN"],
            "path": "Vessel/M4-nut.ipt",
            "signature": plan.signature,
            "confirmed": "1",
        },
    )

    assert refused.status_code == 409
    assert (root / "Vessel" / "M4-nut.ipt").is_file()
    assert read_ledger(root) == ()


def test_quarantine_copy_states_the_survivor_and_is_recoverable(tmp_path: Path) -> None:
    root = make_standard_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    html = client.get("/doctor/standard-parts").get_data(as_text=True)
    form = {
        "token": app.config["FORM_TOKEN"],
        "path": "Probe/parts/M3-nut.ipt",
        "signature": _row_signature(html, "Probe/parts/M3-nut.ipt"),
        "references_checked": "1",
        "survivor": "ContentCenter/Fastners/M3-nut.ipt",
    }
    assert "Surviving copy:\nContentCenter\\Fastners\\M3-nut.ipt" in html.replace("&#10;", "\n")

    wrong = client.post(
        "/doctor/standard-parts/quarantine", data={**form, "survivor": "Stand/M4-nut.ipt"}
    )
    assert wrong.status_code == 409
    assert (root / "Probe" / "parts" / "M3-nut.ipt").is_file()

    done = client.post("/doctor/standard-parts/quarantine", data=form)

    assert done.status_code == 302
    assert "/doctor/standard-parts?quarantined=" in done.headers["Location"]
    assert not (root / "Probe" / "parts" / "M3-nut.ipt").exists()
    assert (root / LIBRARY / "M3-nut.ipt").is_file()
    event = read_quarantine_manifests(root)[0]
    assert event["keep_path"] == "ContentCenter/Fastners/M3-nut.ipt"
    toast = client.get(done.headers["Location"]).get_data(as_text=True)
    assert "Surviving copy: ContentCenter\\Fastners\\M3-nut.ipt" in toast
    assert read_ledger(root) == ()


def test_the_page_script_confirms_each_row_and_skips_per_tab(tmp_path: Path) -> None:
    client = create_app(make_standard_workspace(tmp_path)).test_client()
    script = client.get("/static/dedup.js").get_data(as_text=True)

    assert "form[data-standard-confirm]" in script
    assert "window.confirm(form.dataset.standardConfirm)" in script
    assert "window.sessionStorage" in script
    assert "localStorage" not in script.split("data-standard-parts")[1]
