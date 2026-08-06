import struct
from pathlib import Path

import pytest

from pihti_dedup import geometry_preview
from pihti_dedup.inventor_meta import INVENTOR_EXTENSIONS, Preview

GOOD = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 0.0, 10.0)]
TETRAHEDRON = [
    [GOOD[0], GOOD[1], GOOD[2]],
    [GOOD[0], GOOD[1], GOOD[3]],
    [GOOD[0], GOOD[2], GOOD[3]],
    [GOOD[1], GOOD[2], GOOD[3]],
]


def write_stl(path: Path, triangles=TETRAHEDRON) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"\0" * 80)
        handle.write(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            handle.write(struct.pack("<3f", 0, 0, 1))
            for vertex in triangle:
                handle.write(struct.pack("<3f", *vertex))
            handle.write(b"\0\0")
    return path


def needs_mesh_extra() -> None:
    if ".stl" not in geometry_preview.available_extensions():
        pytest.skip("the 'preview' extra is not installed")


def test_the_extension_sets_do_not_overlap_and_cover_the_advertised_formats() -> None:
    assert geometry_preview.GEOMETRY_EXTENSIONS >= {".stl", ".stp", ".step", ".dwg", ".3mf"}
    assert not geometry_preview.GEOMETRY_EXTENSIONS & INVENTOR_EXTENSIONS
    assert geometry_preview.available_extensions() <= geometry_preview.GEOMETRY_EXTENSIONS
    assert geometry_preview.previewable_extensions() >= INVENTOR_EXTENSIONS


def test_preview_source_names_where_each_extension_gets_its_image() -> None:
    assert geometry_preview.preview_source(".IPT") == "Inventor's embedded thumbnail"
    assert geometry_preview.preview_source(".dwg") == "the DWG's embedded preview"
    assert geometry_preview.preview_source(".step") == "rendered from the geometry"
    assert geometry_preview.preview_source(".dxf") == ""  # the known gap


def test_the_cache_key_moves_with_everything_that_changes_the_bytes(tmp_path: Path) -> None:
    path = tmp_path / "part.stl"
    base = geometry_preview.cache_key(path, 111, 222, 512)

    assert geometry_preview.cache_key(path, 111, 222, 512) == base
    assert geometry_preview.cache_key(path, 112, 222, 512) != base  # modified time
    assert geometry_preview.cache_key(path, 111, 223, 512) != base  # size
    assert geometry_preview.cache_key(path, 111, 222, 256) != base  # render size
    assert geometry_preview.cache_key(tmp_path / "other.stl", 111, 222, 512) != base


def test_the_renderer_version_supersedes_every_stored_key(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "part.stl"
    before = geometry_preview.cache_key(path, 111, 222)
    monkeypatch.setattr(geometry_preview, "RENDERER_VERSION", 99)

    assert geometry_preview.cache_key(path, 111, 222) != before


def test_the_cache_is_sharded_under_the_gitignored_store(tmp_path: Path) -> None:
    store = geometry_preview.preview_store(tmp_path)
    key = "abcdef" + "0" * 58

    assert store == tmp_path / ".pihti-dedup" / "previews"
    assert geometry_preview.cache_path(store, key) == store / "ab" / f"{key}.png"


def test_a_synthetic_stl_renders_to_png_bytes(tmp_path: Path) -> None:
    needs_mesh_extra()
    preview = geometry_preview.render(write_stl(tmp_path / "part.stl"), size=128)

    assert isinstance(preview, Preview)
    assert preview.image_format == "png"
    assert preview.media_type == "image/png"
    assert preview.data[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize(
    "name, payload",
    [
        ("corrupt stl", b"not an stl at all"),
        ("empty stl", b"\0" * 80 + struct.pack("<I", 0)),
    ],
)
def test_unrenderable_input_returns_none_and_never_raises(
    tmp_path: Path, name: str, payload: bytes
) -> None:
    needs_mesh_extra()
    path = tmp_path / "broken.stl"
    path.write_bytes(payload)

    assert geometry_preview.render(path) is None


def test_an_unsupported_or_missing_file_returns_none(tmp_path: Path) -> None:
    assert geometry_preview.render(tmp_path / "part.iam") is None  # Inventor's own job
    assert geometry_preview.render(tmp_path / "gone.stl") is None
    assert geometry_preview.render(tmp_path / "drawing.dxf") is None  # the known gap


def test_a_missing_extra_degrades_to_no_preview_rather_than_an_import_error(
    monkeypatch, tmp_path: Path
) -> None:
    path = write_stl(tmp_path / "part.stl")
    monkeypatch.setattr(geometry_preview, "available_extensions", frozenset)

    assert geometry_preview.render(path) is None
    assert geometry_preview.get_or_render(tmp_path, path, path.stat().st_mtime_ns) is None
    assert not geometry_preview.preview_store(tmp_path).exists()


def test_a_render_is_written_to_disk_once_and_read_back_afterwards(
    monkeypatch, tmp_path: Path
) -> None:
    needs_mesh_extra()
    workspace = tmp_path / "workspace"
    path = write_stl(workspace / "exports" / "part.stl")
    stat = path.stat()

    first = geometry_preview.get_or_render(workspace, path, stat.st_mtime_ns, size=128)
    stored = geometry_preview.cache_path(
        geometry_preview.preview_store(workspace),
        geometry_preview.cache_key(path, stat.st_mtime_ns, stat.st_size, 128),
    )

    assert first is not None
    assert stored.is_file()
    assert stored.read_bytes() == first.data
    assert stored.parent.name == stored.stem[:2]  # sharded
    assert not list(geometry_preview.preview_store(workspace).rglob("*.tmp"))

    def explode(*_args, **_kwargs):
        raise AssertionError("a cache hit must not re-render")

    monkeypatch.setattr(geometry_preview, "render", explode)
    second = geometry_preview.get_or_render(workspace, path, stat.st_mtime_ns, size=128)

    assert second is not None
    assert second.data == first.data


def test_a_touched_file_misses_the_cache_and_is_drawn_again(tmp_path: Path) -> None:
    needs_mesh_extra()
    workspace = tmp_path / "workspace"
    path = write_stl(workspace / "part.stl")
    stat = path.stat()
    geometry_preview.get_or_render(workspace, path, stat.st_mtime_ns, size=128)

    geometry_preview.get_or_render(workspace, path, stat.st_mtime_ns + 1, size=128)

    assert len(list(geometry_preview.preview_store(workspace).rglob("*.png"))) == 2


def test_an_unwritable_cache_still_returns_the_preview(monkeypatch, tmp_path: Path) -> None:
    needs_mesh_extra()
    path = write_stl(tmp_path / "part.stl")

    def refuse(*_args, **_kwargs):
        raise OSError("read-only")

    monkeypatch.setattr(Path, "mkdir", refuse)
    preview = geometry_preview.get_or_render(tmp_path, path, path.stat().st_mtime_ns, size=128)

    assert preview is not None
    assert preview.image_format == "png"


def test_warm_previews_counts_renders_then_reports_the_second_pass_as_cached(
    tmp_path: Path,
) -> None:
    needs_mesh_extra()
    write_stl(tmp_path / "exports" / "a.stl")
    write_stl(tmp_path / "exports" / "b.stl")
    (tmp_path / "exports" / "notes.txt").write_text("ignored", encoding="utf-8")
    seen: list[tuple[int, int, str]] = []

    first = geometry_preview.warm_previews(
        tmp_path, progress=lambda i, n, path, state, _s: seen.append((i, n, state))
    )
    second = geometry_preview.warm_previews(tmp_path)

    assert first.considered == 2
    assert first.rendered == 2
    assert first.cached == 0
    assert first.failed == 0
    assert first.seconds > 0
    assert seen == [(1, 2, "rendered"), (2, 2, "rendered")]
    assert second.rendered == 0
    assert second.cached == 2
    assert second.to_dict()["considered"] == 2


def test_warm_previews_records_a_failure_without_stopping(tmp_path: Path) -> None:
    needs_mesh_extra()
    write_stl(tmp_path / "good.stl")
    (tmp_path / "bad.stl").write_bytes(b"not an stl")

    result = geometry_preview.warm_previews(tmp_path)

    assert result.considered == 2
    assert result.rendered == 1
    assert result.failed == 1
    assert result.failures and "bad.stl" in result.failures[0]
