import json
from pathlib import Path

import pihti_dedup.cli as cli
from pihti_dedup.git_history import PullRequestMerge
from pihti_dedup.legacy import main as legacy_main


def test_scan_command_writes_portable_json(tmp_path: Path, capsys) -> None:
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    (tmp_path / "one" / "part.ipt").write_bytes(b"same")
    (tmp_path / "two" / "part.ipt").write_bytes(b"same")
    output = tmp_path / "inventory.json"

    assert cli.main(["scan", str(tmp_path), "--json", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["root"] == "."
    assert payload["summary"]["exact_groups"] == 1
    assert "same-name/exact-copy groups: 1" in capsys.readouterr().out


def test_legacy_cli_retains_old_summary_and_group_keys(tmp_path: Path, capsys) -> None:
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    (tmp_path / "one" / "part.ipt").write_bytes(b"same")
    (tmp_path / "two" / "part.ipt").write_bytes(b"same")
    output = tmp_path / "legacy.json"

    assert legacy_main([str(tmp_path), "--extensions", ".ipt", "--json", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["root"] == str(tmp_path.resolve())
    assert set(payload["files"][0]) == {"path", "name", "suffix", "size", "mtime_ns", "sha256"}
    assert "hash_duplicates" in payload["groups"]
    assert "same_name_same_size" in payload["groups"]
    assert "hash duplicate groups: 1" in capsys.readouterr().out


def test_merge_cleanup_cli_has_dry_and_guarded_apply_modes(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    canonical = tmp_path / "Canonical" / "part.ipt"
    candidate = tmp_path / "Submission" / "part.ipt"
    canonical.parent.mkdir()
    candidate.parent.mkdir()
    canonical.write_bytes(b"same")
    candidate.write_bytes(b"same")
    merge = PullRequestMerge(
        sha="d" * 40,
        number=3,
        branch="student/update",
        paths=frozenset({"Submission/part.ipt"}),
        folders=("Submission",),
        added_paths=frozenset({"Submission/part.ipt"}),
    )
    monkeypatch.setattr(cli, "recent_pull_request_merges", lambda _root: (merge,))

    assert cli.main(["merge-cleanup", str(tmp_path), "--pr", "3", "--dry"]) == 0
    assert candidate.exists()
    assert "WOULD QUARANTINE Submission\\part.ipt" in capsys.readouterr().out

    assert cli.main(["merge-cleanup", str(tmp_path), "--pr", "3", "--apply"]) == 2
    assert candidate.exists()
    assert "--references-checked" in capsys.readouterr().err

    assert (
        cli.main(
            [
                "merge-cleanup",
                str(tmp_path),
                "--pr",
                "3",
                "--apply",
                "--references-checked",
            ]
        )
        == 0
    )
    assert not candidate.exists()
    assert canonical.exists()
    assert "QUARANTINED 1 files" in capsys.readouterr().out
