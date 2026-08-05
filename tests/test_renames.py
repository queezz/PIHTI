import json
from pathlib import Path

import pytest

from pihti_dedup.renames import (
    LEDGER_RELATIVE,
    RenameEntry,
    RenameError,
    execute_rename,
    ledger_path,
    plan_rename,
    read_ledger,
    set_settled,
)
from pihti_dedup.whereused import WhereUsed, build_index


def assembly_bytes(*stored_paths: str) -> bytes:
    """An assembly body: filler with UTF-16LE reference paths embedded in it."""

    payload = bytearray(b"\xde\xad" * 4)
    for stored in stored_paths:
        payload += b"\x00\x00" + stored.encode("utf-16-le") + b"\x00\x00"
    return bytes(payload)


def make_workspace(root: Path) -> Path:
    parts = root / "BoronProbe" / "parts"
    parts.mkdir(parents=True)
    (parts / "bearing.ipt").write_bytes(b"geometry")
    (parts / "shaft.ipt").write_bytes(b"geometry")
    assembly = root / "BoronProbe" / "probe.iam"
    assembly.write_bytes(assembly_bytes("parts\\bearing.ipt", "parts\\shaft.ipt"))
    return root


def empty_index(root: Path) -> WhereUsed:
    return WhereUsed(root=root, referrers={}, documents=0)


def test_a_clean_rename_moves_the_file_and_records_the_ledger(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    index = build_index(root)

    plan = plan_rename(root, "BoronProbe/parts/bearing.ipt", "probe_bearing", index=index)
    assert plan.new_name == "probe_bearing.ipt"  # extension appended, never chosen by the user
    assert plan.referrers == ("BoronProbe/probe.iam",)
    assert plan.will_prompt is True
    assert plan.needs_confirmation is False

    result = execute_rename(root, plan)

    assert not (root / "BoronProbe/parts/bearing.ipt").exists()
    assert (root / "BoronProbe/parts/probe_bearing.ipt").read_bytes() == b"geometry"
    entries = read_ledger(root)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.id == result.entry.id and entry.id
    assert entry.old_path == "BoronProbe/parts/bearing.ipt"
    assert entry.new_path == "BoronProbe/parts/probe_bearing.ipt"
    assert entry.where_used == ("BoronProbe/probe.iam",)
    assert entry.will_prompt is True
    assert entry.settled is False
    assert ledger_path(root) == root / LEDGER_RELATIVE


def test_the_sidecar_follows_the_file(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    companion = root / "BoronProbe" / "parts" / "bearing.ipt.md"
    companion.write_text("---\nstatus: draft\n---\n\nWhy.\n", encoding="utf-8")

    plan = plan_rename(root, "BoronProbe/parts/bearing.ipt", "probe_bearing", index=empty_index(root))
    result = execute_rename(root, plan)

    assert result.sidecar_moved is True
    assert not companion.exists()
    moved = root / "BoronProbe" / "parts" / "probe_bearing.ipt.md"
    assert moved.read_text(encoding="utf-8") == "---\nstatus: draft\n---\n\nWhy.\n"
    assert read_ledger(root)[0].sidecar_moved is True


def test_a_name_already_in_the_workspace_is_refused(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    other = root / "Plasma Vessel"
    other.mkdir()
    (other / "probe_bearing.ipt").write_bytes(b"someone else")

    with pytest.raises(RenameError) as refused:
        plan_rename(root, "BoronProbe/parts/bearing.ipt", "probe_bearing", index=empty_index(root))

    assert "already exists in the workspace" in str(refused.value)
    assert "Plasma Vessel/probe_bearing.ipt" in str(refused.value)
    assert (root / "BoronProbe/parts/bearing.ipt").exists()


def test_a_surviving_old_name_is_a_silent_rebind_and_needs_confirmation(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    twin = root / "Plasma Vessel" / "parts"
    twin.mkdir(parents=True)
    (twin / "bearing.ipt").write_bytes(b"a different bearing")
    index = build_index(root)

    plan = plan_rename(root, "BoronProbe/parts/bearing.ipt", "probe_bearing", index=index)

    assert plan.old_name_survivors == ("Plasma Vessel/parts/bearing.ipt",)
    assert plan.needs_confirmation is True
    assert plan.will_prompt is False

    with pytest.raises(RenameError) as refused:
        execute_rename(root, plan)
    assert "rebind to it silently" in str(refused.value)
    assert (root / "BoronProbe/parts/bearing.ipt").exists()

    execute_rename(root, plan, confirmed=True)

    assert (root / "BoronProbe/parts/probe_bearing.ipt").exists()
    entry = read_ledger(root)[0]
    assert entry.will_prompt is False
    assert entry.where_used == ("BoronProbe/probe.iam",)


def test_the_extension_is_fixed_and_illegal_names_are_refused(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    index = empty_index(root)

    def refuse(name: str) -> str:
        with pytest.raises(RenameError) as error:
            plan_rename(root, "BoronProbe/parts/bearing.ipt", name, index=index)
        return str(error.value)

    assert "the extension is fixed" in refuse("bearing.iam")
    assert "a filename cannot contain" in refuse("sub/bearing")
    assert "a filename cannot contain" in refuse("bear:ing")
    assert "reserved Windows device name" in refuse("con.ipt")
    assert "a new filename is required" in refuse("   ")
    assert "that is the same filename" in refuse("bearing.ipt")
    assert "case-insensitively" in refuse("Bearing.IPT")
    assert (root / "BoronProbe/parts/bearing.ipt").exists()


def test_a_path_past_the_windows_ceiling_is_refused(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)

    with pytest.raises(RenameError) as refused:
        plan_rename(
            root,
            "BoronProbe/parts/bearing.ipt",
            "x" * 260,
            index=empty_index(root),
        )

    assert "stop being reliable past 260" in str(refused.value)


def test_only_inventor_documents_can_be_renamed(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    export = root / "BoronProbe" / "bearing.stl"
    export.write_bytes(b"mesh")

    with pytest.raises(RenameError) as refused:
        plan_rename(root, "BoronProbe/bearing.stl", "probe_bearing", index=empty_index(root))

    assert "only Inventor documents can be renamed" in str(refused.value)


def test_the_ledger_round_trips_and_survives_a_hand_edited_line(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    plan = plan_rename(root, "BoronProbe/parts/bearing.ipt", "probe_bearing", index=empty_index(root))
    entry = execute_rename(root, plan).entry
    with ledger_path(root).open("a", encoding="utf-8") as handle:
        handle.write("this line is not JSON\n\n")

    entries = read_ledger(root)
    assert len(entries) == 1

    settled = set_settled(root, entry.id, True)
    assert settled.settled is True
    assert read_ledger(root)[0].settled is True

    reopened = set_settled(root, entry.id, False)
    assert reopened.settled is False
    assert read_ledger(root)[0].settled is False

    with pytest.raises(RenameError):
        set_settled(root, "0000000000000000", True)


def test_a_ledger_line_is_json_with_workspace_relative_paths(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    plan = plan_rename(root, "BoronProbe/parts/bearing.ipt", "probe_bearing", index=build_index(root))
    execute_rename(root, plan)

    line = ledger_path(root).read_text(encoding="utf-8").strip()
    payload = json.loads(line)

    assert payload["old_path"] == "BoronProbe/parts/bearing.ipt"
    assert payload["new_path"] == "BoronProbe/parts/probe_bearing.ipt"
    assert str(root) not in line  # never a machine-specific path in a tracked file
    assert RenameEntry.from_dict(payload).new_folder == "BoronProbe/parts"
