"""The machine-local cache root: where it is, whose it is, and when it is refused."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from pihti_dedup import cache_root, geometry_preview, mesh_cache


def test_the_default_root_is_under_localappdata_on_windows(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(cache_root.ENV_VAR, raising=False)
    local = tmp_path / "AppData" / "Local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    workspace = tmp_path / "PIHTI"
    workspace.mkdir()

    base = cache_root.default_base(platform="win32")
    assert base == local / "pihti-dedup"
    if sys.platform.startswith("win"):
        root = cache_root.cache_root(workspace)
        assert root.parent == (local / "pihti-dedup").resolve()
        assert not root.exists()  # computing the root creates nothing


def test_elsewhere_the_default_is_the_home_cache_folder(monkeypatch) -> None:
    monkeypatch.delenv(cache_root.ENV_VAR, raising=False)

    base = cache_root.default_base(platform="linux")

    assert base == Path.home() / ".cache" / "pihti-dedup"


def test_the_environment_override_wins(monkeypatch, tmp_path: Path) -> None:
    override = tmp_path / "elsewhere"
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.setenv(cache_root.ENV_VAR, str(override))
    workspace = tmp_path / "PIHTI"
    workspace.mkdir()

    assert cache_root.default_base(platform="win32") == override
    assert cache_root.default_base(platform="linux") == override
    assert cache_root.cache_root(workspace).parent == override.resolve()


def test_the_workspace_id_is_its_name_and_twelve_hex_of_its_resolved_path(tmp_path: Path) -> None:
    first = tmp_path / "one" / "PIHTI"
    second = tmp_path / "two" / "PIHTI"
    first.mkdir(parents=True)
    second.mkdir(parents=True)

    first_id = cache_root.workspace_id(first)
    second_id = cache_root.workspace_id(second)

    assert re.fullmatch(r"PIHTI-[0-9a-f]{12}", first_id)
    assert first_id != second_id  # same folder name, different checkouts
    assert cache_root.cache_root(first) != cache_root.cache_root(second)
    # One workspace spelled two ways is one cache.
    assert cache_root.workspace_id(first / ".." / "PIHTI") == first_id


def test_a_virtualized_appdata_base_is_refused_naming_the_path(monkeypatch, tmp_path: Path) -> None:
    packaged = (
        tmp_path / "AppData" / "Local" / "Packages" / "Some.App_8wekyb3d8bbwe" / "LocalCache"
        / "Local" / "pihti-dedup"
    )
    monkeypatch.setenv(cache_root.ENV_VAR, str(packaged))
    workspace = tmp_path / "PIHTI"
    workspace.mkdir()

    with pytest.raises(cache_root.CacheRootError) as refused:
        cache_root.cache_root(workspace)

    assert str(packaged.resolve()) in str(refused.value)
    assert "LocalCache" in str(refused.value)
    with pytest.raises(cache_root.CacheRootError):
        geometry_preview.preview_store(workspace)
    assert not packaged.exists()


def test_an_ordinary_appdata_path_is_not_mistaken_for_a_virtualized_one() -> None:
    assert not cache_root.is_virtualized(r"C:\Users\someone\AppData\Local\pihti-dedup")
    assert not cache_root.is_virtualized(r"C:\Users\someone\AppData\Local\Packages\pihti-dedup")
    assert cache_root.is_virtualized(
        r"C:\Users\someone\AppData\Local\Packages\X_1\LocalCache\Local\pihti-dedup"
    )


def test_previews_and_meshes_live_in_their_own_folders_under_the_root(tmp_path: Path) -> None:
    workspace = tmp_path / "PIHTI"
    workspace.mkdir()
    root = cache_root.cache_root(workspace)

    assert geometry_preview.preview_store(workspace) == root / "previews"
    assert mesh_cache.mesh_store(workspace) == root / "meshes"
    assert workspace not in root.parents
