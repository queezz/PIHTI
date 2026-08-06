import json
import struct
from pathlib import Path

import pytest

import pihti_dedup.cli as cli
import pihti_dedup.web as web
from pihti_dedup import geometry_preview
from pihti_dedup.git_history import PullRequestMerge
from pihti_dedup.legacy import main as legacy_main
from pihti_dedup.sidecar import read_sidecar

TETRAHEDRON = [
    [(0, 0, 0), (10, 0, 0), (0, 10, 0)],
    [(0, 0, 0), (10, 0, 0), (0, 0, 10)],
    [(0, 0, 0), (0, 10, 0), (0, 0, 10)],
    [(10, 0, 0), (0, 10, 0), (0, 0, 10)],
]


def write_stl(path: Path, triangles=TETRAHEDRON) -> Path:
    with open(path, "wb") as handle:
        handle.write(b"\0" * 80)
        handle.write(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            handle.write(struct.pack("<3f", 0, 0, 1))
            for vertex in triangle:
                handle.write(struct.pack("<3f", *vertex))
            handle.write(b"\0\0")
    return path


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


def test_serve_opens_the_catalog_as_the_landing_view(monkeypatch, tmp_path: Path, capsys) -> None:
    opened: list[str] = []
    runs: list[dict] = []

    class ImmediateTimer:
        def __init__(self, _delay, callback) -> None:
            self.callback = callback

        def start(self) -> None:
            self.callback()

    class FakeApp:
        def run(self, **kwargs) -> None:
            runs.append(kwargs)

    monkeypatch.setattr(cli.threading, "Timer", ImmediateTimer)
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    monkeypatch.setattr(web, "create_app", lambda _workspace: FakeApp())

    assert cli.main(["serve", str(tmp_path), "--open"]) == 0
    assert opened == ["http://127.0.0.1:4185/catalog"]
    assert runs == [
        {"host": "127.0.0.1", "port": 4185, "threaded": True, "use_reloader": False}
    ]
    assert "PIHTI CAD viewer: http://127.0.0.1:4185/catalog" in capsys.readouterr().out


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


def test_warm_previews_builds_the_disk_cache_and_reports_counts(tmp_path: Path, capsys) -> None:
    if ".stl" not in geometry_preview.available_extensions():
        pytest.skip("the 'preview' extra is not installed")
    exports = tmp_path / "BoronProbe" / "exports"
    exports.mkdir(parents=True)
    write_stl(exports / "head.stl")
    (exports / "head.ipt").write_bytes(b"cad")  # Inventor carries its own thumbnail
    report = tmp_path / "warm.json"

    assert cli.main(["warm-previews", str(tmp_path), "--json", str(report)]) == 0

    out = capsys.readouterr().out
    assert "renderable extensions: " in out
    assert ".stl" in out.splitlines()[1]
    assert "[   1/1] rendered" in out
    assert "considered 1 · rendered 1 · already cached 0 · failed 0" in out
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["rendered"] == 1
    assert payload["failures"] == []
    assert len(list((tmp_path / ".pihti-dedup" / "previews").rglob("*.png"))) == 1

    assert cli.main(["warm-previews", str(tmp_path), "--quiet"]) == 0
    second = capsys.readouterr().out
    assert "already cached 1" in second
    assert "[   1/1]" not in second


def test_warm_previews_reports_a_file_it_could_not_draw(tmp_path: Path, capsys) -> None:
    if ".stl" not in geometry_preview.available_extensions():
        pytest.skip("the 'preview' extra is not installed")
    (tmp_path / "broken.stl").write_bytes(b"not an stl")

    assert cli.main(["warm-previews", str(tmp_path), "--quiet"]) == 1
    captured = capsys.readouterr()

    assert "failed 1" in captured.out
    assert "broken.stl" in captured.err


def test_meta_seed_previews_then_writes_missing_sidecars(tmp_path: Path, capsys) -> None:
    parts = tmp_path / "BoronProbe" / "parts"
    parts.mkdir(parents=True)
    (parts / "bearing.ipt").write_bytes(b"cad")
    (parts / "probe.iam").write_bytes(b"cad")
    (parts / "export.stl").write_bytes(b"mesh")
    (parts / "probe.iam.md").write_text("---\nstatus: draft\n---\n\nKeep.\n", encoding="utf-8")

    assert cli.main(["meta", "seed", str(tmp_path), "--dry"]) == 0
    dry = capsys.readouterr().out
    assert "Inventor documents: 2" in dry
    assert "missing sidecars: 1" in dry
    assert "WOULD SEED BoronProbe\\parts\\bearing.ipt.md" in dry
    assert not (parts / "bearing.ipt.md").exists()

    assert cli.main(["meta", "seed", str(tmp_path), "--apply"]) == 0

    assert "SEEDED 1 sidecars" in capsys.readouterr().out
    seeded = read_sidecar(parts / "bearing.ipt.md")
    assert seeded is not None
    assert set(seeded.frontmatter) == {
        "part_number",
        "material",
        "status",
        "tags",
        "supersedes",
        "seeded_from_iproperties",
    }
    assert not (parts / "export.stl.md").exists()
    untouched = (parts / "probe.iam.md").read_text(encoding="utf-8")
    assert untouched == "---\nstatus: draft\n---\n\nKeep.\n"
