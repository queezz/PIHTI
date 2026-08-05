from pathlib import Path

from pihti_dedup.inventory import CAD_EXTENSIONS, scan_paths, scan_workspace


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


def test_newver_exact_pair_gets_conservative_characterization(tmp_path: Path) -> None:
    _write(tmp_path / "Parts" / "Part5.ipt", b"same")
    _write(tmp_path / "Parts" / "Part5.newVer.ipt", b"same")

    group = scan_workspace(tmp_path).renamed_groups[0]

    assert group.characterization == "newver"
    assert group.title == "newVer pair — identical bytes"
    assert group.to_dict()["characterization"] == "newver"
