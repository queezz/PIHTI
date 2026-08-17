import os
import subprocess
from pathlib import Path

import pytest

from pihti_dedup.git_filename_history import (
    GitHistoryError,
    materialize_historical_blob,
    query_filename_history,
)


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    return result.stdout.decode("utf-8").strip()


def commit(repo: Path, subject: str, date: str) -> str:
    environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
    }
    git(
        repo,
        "-c",
        "user.name=PIHTI test",
        "-c",
        "user.email=pihti@example.invalid",
        "commit",
        "-m",
        subject,
        env=environment,
    )
    return git(repo, "rev-parse", "HEAD")


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repository"
    repo.mkdir()
    git(repo, "init")
    return repo


def test_exact_basename_history_reports_add_modify_and_rename(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    source = repo / "Imported" / "Body.ipt"
    source.parent.mkdir()
    source.write_bytes(b"first geometry")
    git(repo, "add", "--", "Imported/Body.ipt")
    added = commit(repo, "Add imported body", "2026-08-01T10:00:00+09:00")

    source.write_bytes(b"second geometry")
    git(repo, "add", "--", "Imported/Body.ipt")
    commit(repo, "Resave imported body", "2026-08-02T10:00:00+09:00")

    git(repo, "mv", "Imported/Body.ipt", "Imported/Valve housing.ipt")
    commit(repo, "Name the valve housing", "2026-08-03T10:00:00+09:00")

    history = query_filename_history(repo, "Body.ipt")

    assert history.found is True
    assert [item.status[:1] for item in history.occurrences] == ["R", "M", "A"]
    assert history.occurrences[0].path == "Imported/Body.ipt"
    assert history.occurrences[0].rename_destination == "Imported/Valve housing.ipt"
    assert history.occurrences[-1].commit == added
    assert history.occurrences[-1].committed_at == "2026-08-01T10:00:00+09:00"
    assert history.occurrences[-1].subject == "Add imported body"
    assert materialize_historical_blob(repo, added, "Imported/Body.ipt") == b"first geometry"

    destination_history = query_filename_history(repo, "Valve housing.ipt")
    assert destination_history.found is True
    assert destination_history.occurrences[0].rename_destination == (
        "Imported/Valve housing.ipt"
    )


def test_unicode_paths_round_trip_and_never_tracked_is_distinct(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    main_branch = git(repo, "symbolic-ref", "--short", "HEAD")
    part = repo / "部品" / "本体.ipt"
    part.parent.mkdir()
    part.write_bytes("形状".encode())
    git(repo, "add", "--", "部品/本体.ipt")
    commit(repo, "日本語の部品を追加", "2026-08-04T12:00:00+09:00")

    git(repo, "checkout", "-b", "historical-import")
    branch_only = repo / "旧部品" / "枝だけ.ipt"
    branch_only.parent.mkdir()
    branch_only.write_bytes(b"branch-only geometry")
    git(repo, "add", "--", "旧部品/枝だけ.ipt")
    commit(repo, "Keep a branch-only import", "2026-08-04T13:00:00+09:00")
    git(repo, "checkout", main_branch)

    found = query_filename_history(repo, "本体.ipt")
    other_ref = query_filename_history(repo, "枝だけ.ipt")
    absent = query_filename_history(repo, "存在しない.ipt")

    assert found.found is True
    assert found.occurrences[0].path == "部品/本体.ipt"
    assert found.occurrences[0].subject == "日本語の部品を追加"
    assert other_ref.found is True
    assert other_ref.occurrences[0].path == "旧部品/枝だけ.ipt"
    assert absent.found is False
    assert absent.occurrences == ()


def test_blob_materialization_rejects_revision_and_path_injection(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    part = repo / "part.ipt"
    part.write_bytes(b"geometry")
    git(repo, "add", "--", "part.ipt")
    revision = commit(repo, "Add part", "2026-08-05T12:00:00+09:00")

    with pytest.raises(ValueError, match="full hexadecimal"):
        materialize_historical_blob(repo, "--help", "part.ipt")
    with pytest.raises(ValueError, match="traversal-free"):
        materialize_historical_blob(repo, revision, "../part.ipt")
    with pytest.raises(ValueError, match="basename"):
        query_filename_history(repo, "folder/part.ipt")
    with pytest.raises(GitHistoryError):
        materialize_historical_blob(repo, "f" * 40, "part.ipt")
