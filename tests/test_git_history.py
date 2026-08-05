import subprocess
from pathlib import Path

from pihti_dedup.git_history import recent_pull_request_merges


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=PIHTI test",
            "-c",
            "user.email=pihti-test@example.invalid",
            *args,
        ],
        check=True,
        capture_output=True,
    )


def test_recent_pull_request_merges_reports_current_cad_paths(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    _git(root, "init", "-b", "master")
    (root / "README.md").write_text("PIHTI\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "Start archive")

    _git(root, "switch", "-c", "mizuno-update")
    part = root / "BoronProbe_2026" / "parts" / "bearing.ipt"
    part.parent.mkdir(parents=True)
    part.write_bytes(b"bearing")
    (part.parent / "notes.txt").write_text("student note\n", encoding="utf-8")
    _git(root, "add", "BoronProbe_2026")
    _git(root, "commit", "-m", "Add bearing")
    _git(root, "switch", "master")
    _git(
        root,
        "merge",
        "--no-ff",
        "mizuno-update",
        "-m",
        "Merge pull request #7 from mizuno/cad-update",
    )

    merges = recent_pull_request_merges(root)

    assert len(merges) == 1
    assert merges[0].number == 7
    assert merges[0].branch == "mizuno/cad-update"
    assert merges[0].paths == frozenset({"BoronProbe_2026/parts/bearing.ipt"})
    assert merges[0].added_paths == frozenset({"BoronProbe_2026/parts/bearing.ipt"})
    assert merges[0].folders == ("BoronProbe_2026",)


def test_non_git_workspace_has_no_merge_context(tmp_path: Path) -> None:
    assert recent_pull_request_merges(tmp_path) == ()
