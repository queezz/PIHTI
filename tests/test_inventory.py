import os
from pathlib import Path

from pihti_dedup.cleanup import plan_member_cleanup
from pihti_dedup.inventory import CAD_EXTENSIONS, newver_leftovers, scan_paths, scan_workspace


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def make_workspace(root: Path) -> Path:
    _write(root / "SystemA" / "part.ipt", b"revision-a")
    _write(root / "SystemB" / "part.ipt", b"revision-b")
    _write(root / "SystemA" / "exact.iam", b"same assembly")
    _write(root / "SystemB" / "exact.iam", b"same assembly")
    _write(root / "SystemA" / "source.stp", b"same geometry")
    _write(root / "SystemB" / "renamed.step", b"same geometry")
    _write(root / "SystemA" / "notes.txt", b"not CAD")
    _write(root / "OldVersions" / "part.ipt", b"old")
    _write(root / "staging" / "part.ipt", b"incoming")
    _write(root / "bellows" / "Design Data" / "vendor.ipt", b"vendor")
    _write(root / "bellows" / "Templates" / "template.ipt", b"template")
    return root


def test_scan_classifies_filename_and_hash_groups(tmp_path: Path) -> None:
    inventory = scan_workspace(make_workspace(tmp_path))

    assert inventory.summary["files"] == 6
    assert inventory.summary["filename_groups"] == 2
    assert inventory.summary["collision_groups"] == 1
    assert inventory.summary["exact_groups"] == 1
    assert inventory.summary["renamed_groups"] == 1

    groups = {group.title.casefold(): group for group in inventory.filename_groups}
    assert groups["part.ipt"].kind == "collision"
    assert groups["part.ipt"].cross_folder is True
    assert groups["exact.iam"].kind == "exact"
    assert groups["exact.iam"].redundant_bytes == len(b"same assembly")

    renamed = inventory.renamed_groups[0]
    assert renamed.kind == "renamed"
    assert renamed.names == ("renamed.step", "source.stp")


def test_default_scope_records_exclusions_and_vendor_is_opt_in(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    default = scan_workspace(root)
    included = scan_workspace(root, include_vendor=True)

    excluded = {item.path: item.reason for item in default.excluded}
    assert excluded["OldVersions"] == "Inventor save history"
    assert excluded["staging"] == "excluded directory"
    assert excluded["bellows/Design Data"] == "Pack-and-Go vendor support"
    assert excluded["bellows/Templates"] == "Pack-and-Go vendor support"
    assert included.summary["files"] == default.summary["files"] + 2


def test_payload_is_portable_and_extensions_are_cad_only(tmp_path: Path) -> None:
    inventory = scan_workspace(make_workspace(tmp_path))
    payload = inventory.to_dict()

    assert payload["root"] == "."
    assert str(tmp_path) not in str(payload)
    assert payload["scope"]["extensions"] == sorted(CAD_EXTENSIONS)
    assert all(not record["path"].endswith("notes.txt") for record in payload["files"])


def test_all_files_scope_and_overlapping_roots_are_reported_correctly(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    inventory = scan_workspace(root, extensions=None)
    overlapping = scan_paths([root, root / "SystemA"], display_root=root)

    assert inventory.to_dict()["scope"]["extensions"] is None
    assert any(record.path.endswith("notes.txt") for record in inventory.records)
    assert len({record.path for record in overlapping.records}) == len(overlapping.records)


def test_no_hash_marks_repeated_names_unverified(tmp_path: Path) -> None:
    inventory = scan_workspace(make_workspace(tmp_path), hash_files=False)

    assert {group.kind for group in inventory.filename_groups} == {"unverified"}
    assert inventory.renamed_groups == ()


def _same_time(*paths: Path, stamp: int = 1_750_458_966_208_000_000) -> None:
    for path in paths:
        os.utime(path, ns=(stamp, stamp))


def test_newver_exact_pair_gets_conservative_characterization(tmp_path: Path) -> None:
    _write(tmp_path / "Parts" / "Part5.ipt", b"same")
    _write(tmp_path / "Parts" / "Part5.newVer.ipt", b"same")
    _same_time(tmp_path / "Parts" / "Part5.ipt", tmp_path / "Parts" / "Part5.newVer.ipt")

    group = scan_workspace(tmp_path).renamed_groups[0]

    assert group.characterization == "newver"
    assert group.title == "Inventor save leftover — identical to Part5.ipt"
    assert group.to_dict()["characterization"] == "newver"


def test_a_same_name_group_splits_into_its_identical_copies(tmp_path: Path) -> None:
    """{A, A, B}: the two A members are one identical group on Duplicates, B is
    a name clash only, and the summary still counts the collision."""

    _write(tmp_path / "TempController" / "Body.ipt", b"twin")
    _write(tmp_path / "TempController-v2" / "Body.ipt", b"twin")
    _write(tmp_path / "GX12" / "Body.ipt", b"other body")

    inventory = scan_workspace(tmp_path)

    assert inventory.summary["collision_groups"] == 1
    assert inventory.to_dict()["summary"]["collision_groups"] == 1
    assert [group.kind for group in inventory.filename_groups] == ["collision"]
    shown = inventory.duplicate_groups
    assert [group.kind for group in shown] == ["exact"]
    assert shown[0].characterization == "split"
    assert shown[0].title == "Body.ipt"
    assert [record.path for record in shown[0].records] == [
        "TempController-v2/Body.ipt",
        "TempController/Body.ipt",
    ]
    assert all(group.kind != "collision" for group in shown)
    assert inventory.name_clash_groups == inventory.filename_groups
    # The split group is found by id, and its guarded member delete keeps the twin.
    assert inventory.find_group(shown[0].id) == shown[0]
    plan = plan_member_cleanup(inventory, group_id=shown[0].id, path="TempController/Body.ipt")
    assert plan.group_kind == "exact"
    assert plan.candidate.keep_paths == ("TempController-v2/Body.ipt",)


def test_only_the_newver_member_of_a_leftover_pair_is_the_leftover(tmp_path: Path) -> None:
    base = tmp_path / "Parts" / "Part5.ipt"
    leftover = tmp_path / "Parts" / "Part5.newVer.ipt"
    _write(base, b"same")
    _write(leftover, b"same")
    _same_time(base, leftover)

    group = scan_workspace(tmp_path).renamed_groups[0]
    pairs = newver_leftovers(group.records)

    assert [(item.path, original.path) for item, original in pairs] == [
        ("Parts/Part5.newVer.ipt", "Parts/Part5.ipt")
    ]


def test_differing_and_orphan_leftovers_are_interrupted_saves(tmp_path: Path) -> None:
    _write(tmp_path / "Parts" / "Bracket.ipt", b"original")
    _write(tmp_path / "Parts" / "Bracket.newVer.ipt", b"newer work")
    _write(tmp_path / "Parts" / "Gone.newVer.ipt", b"lonely")
    _write(tmp_path / "Other" / "Bracket.ipt", b"newer work")  # same bytes, other folder

    inventory = scan_workspace(tmp_path)

    found = {(item.path, item.base_path, item.state) for item in inventory.save_leftovers}
    assert found == {
        ("Parts/Bracket.newVer.ipt", "Parts/Bracket.ipt", "differs"),
        ("Parts/Gone.newVer.ipt", "Parts/Gone.ipt", "orphan"),
    }
    # A differing pair is never a save-leftover card on Duplicates.
    assert all(group.characterization != "newver" for group in inventory.duplicate_groups)
