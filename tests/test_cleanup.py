import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pihti_dedup.cleanup import (
    execute_cleanup,
    execute_member_cleanup,
    plan_member_cleanup,
    plan_merge_exact_cleanup,
)
from pihti_dedup.git_history import PullRequestMerge
from pihti_dedup.inventory import scan_workspace


def _write(path: Path, content: bytes = b"same") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _merge(*added_paths: str) -> PullRequestMerge:
    paths = frozenset(added_paths)
    return PullRequestMerge(
        sha="c" * 40,
        number=3,
        branch="student/update",
        paths=paths,
        folders=tuple(sorted({path.split("/", 1)[0] for path in paths})),
        added_paths=paths,
    )


def test_plan_only_targets_added_exact_copy_with_outside_survivor(tmp_path: Path) -> None:
    _write(tmp_path / "Canonical" / "part.ipt")
    _write(tmp_path / "Submission" / "part.ipt")

    plan = plan_merge_exact_cleanup(scan_workspace(tmp_path), _merge("Submission/part.ipt"))

    assert [candidate.path for candidate in plan.candidates] == ["Submission/part.ipt"]
    assert plan.candidates[0].keep_paths == ("Canonical/part.ipt",)
    assert plan.protected_groups == 0
    assert plan.to_dict()["dry_run"] is True


def test_plan_protects_group_when_every_copy_was_added_by_merge(tmp_path: Path) -> None:
    _write(tmp_path / "SubmissionA" / "part.ipt")
    _write(tmp_path / "SubmissionB" / "part.ipt")

    plan = plan_merge_exact_cleanup(
        scan_workspace(tmp_path),
        _merge("SubmissionA/part.ipt", "SubmissionB/part.ipt"),
    )

    assert plan.candidates == ()
    assert plan.protected_groups == 1


def test_apply_requires_reference_check_and_writes_recovery_manifest(tmp_path: Path) -> None:
    _write(tmp_path / "Canonical" / "part.ipt")
    candidate = tmp_path / "Submission" / "part.ipt"
    _write(candidate)
    plan = plan_merge_exact_cleanup(scan_workspace(tmp_path), _merge("Submission/part.ipt"))

    with pytest.raises(ValueError, match="references"):
        execute_cleanup(tmp_path, plan, references_checked=False)
    assert candidate.exists()

    execution = execute_cleanup(
        tmp_path,
        plan,
        references_checked=True,
        now=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
    )

    assert not candidate.exists()
    assert (tmp_path / "Canonical" / "part.ipt").exists()
    assert execution.manifest == ".pihti-dedup/quarantine/20260805T120000Z-pr-3/manifest.json"
    manifest = json.loads((tmp_path / execution.manifest).read_text(encoding="utf-8"))
    assert manifest["files"][0]["path"] == "Submission/part.ipt"
    assert manifest["files"][0]["keep_paths"] == ["Canonical/part.ipt"]


def test_apply_refuses_candidate_that_changed_after_preview(tmp_path: Path) -> None:
    _write(tmp_path / "Canonical" / "part.ipt")
    candidate = tmp_path / "Submission" / "part.ipt"
    _write(candidate)
    plan = plan_merge_exact_cleanup(scan_workspace(tmp_path), _merge("Submission/part.ipt"))
    candidate.write_bytes(b"changed")

    with pytest.raises(ValueError, match="changed after preview"):
        execute_cleanup(tmp_path, plan, references_checked=True)

    assert candidate.exists()


def test_apply_refuses_timestamp_drift_even_when_bytes_are_unchanged(tmp_path: Path) -> None:
    _write(tmp_path / "Canonical" / "part.ipt")
    candidate = tmp_path / "Submission" / "part.ipt"
    _write(candidate)
    plan = plan_merge_exact_cleanup(scan_workspace(tmp_path), _merge("Submission/part.ipt"))
    stat = candidate.stat()
    os.utime(
        candidate,
        ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000),
    )

    with pytest.raises(ValueError, match="changed after preview"):
        execute_cleanup(tmp_path, plan, references_checked=True)

    assert candidate.exists()


def test_member_cleanup_preserves_identical_survivor_and_manifest(tmp_path: Path) -> None:
    base = tmp_path / "Parts" / "Part5.ipt"
    artifact = tmp_path / "Parts" / "Part5.newVer.ipt"
    _write(base)
    _write(artifact)
    inventory = scan_workspace(tmp_path)
    group = inventory.renamed_groups[0]

    plan = plan_member_cleanup(inventory, group_id=group.id, path="Parts/Part5.newVer.ipt")
    execution = execute_member_cleanup(
        tmp_path,
        plan,
        references_checked=True,
        now=datetime(2026, 8, 5, 13, 0, tzinfo=timezone.utc),
    )

    assert base.exists()
    assert not artifact.exists()
    assert execution.moved == ("Parts/Part5.newVer.ipt",)
    manifest = json.loads((tmp_path / execution.manifest).read_text(encoding="utf-8"))
    assert manifest["source"] == "manual-member"
    assert manifest["files"][0]["mtime_ns"] == plan.candidate.mtime_ns
    assert manifest["files"][0]["keep_paths"] == ["Parts/Part5.ipt"]


def test_member_cleanup_rejects_different_byte_collision(tmp_path: Path) -> None:
    _write(tmp_path / "A" / "part.ipt", b"a")
    _write(tmp_path / "B" / "part.ipt", b"b")
    inventory = scan_workspace(tmp_path)
    group = inventory.filename_groups[0]

    with pytest.raises(ValueError, match="byte-identical"):
        plan_member_cleanup(inventory, group_id=group.id, path="B/part.ipt")
