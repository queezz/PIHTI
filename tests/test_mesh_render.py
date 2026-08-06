"""Degenerate and adversarial input handling for the mesh renderer.

Ported from the 2026-08-05 spike's `test_degenerate.py`. Every fixture is
synthesized here: no CAD binary from the workspace is committed as a fixture.
"""

import struct
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("PIL")

from pihti_dedup import mesh_render  # noqa: E402
from pihti_dedup.mesh_render import EmptyMeshError  # noqa: E402

NAN = float("nan")
INF = float("inf")
GOOD = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]


def binary_stl(path: Path, triangles) -> Path:
    with open(path, "wb") as handle:
        handle.write(b"\0" * 80)
        handle.write(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            handle.write(struct.pack("<3f", 0, 0, 1))
            for vertex in triangle:
                handle.write(struct.pack("<3f", *vertex))
            handle.write(b"\0\0")
    return path


def render(triangles):
    return mesh_render.render_triangles(triangles, size=128, ssaa=1)


@pytest.mark.parametrize(
    "name, triangles",
    [
        ("zero triangles", []),
        ("all triangles collinear", [[(0, 0, 0), (1, 1, 1), (2, 2, 2)]] * 10),
        ("all vertices identical", [[(1, 1, 1), (1, 1, 1), (1, 1, 1)]] * 4),
        ("NaN coordinates only", [[(NAN, 0, 0), (1, 0, 0), (0, 1, 0)]]),
    ],
)
def test_a_binary_stl_with_no_usable_geometry_raises_empty_mesh(
    tmp_path: Path, name: str, triangles
) -> None:
    path = binary_stl(tmp_path / "degenerate.stl", triangles)

    with pytest.raises(EmptyMeshError):
        render(mesh_render.load_stl(path))


@pytest.mark.parametrize(
    "name, payload",
    [
        ("truncated body", b"\0" * 80 + struct.pack("<I", 5000)),  # claims 5000, carries none
        ("not an STL at all", b"this is not an STL at all"),
        ("ASCII STL with no facets", b"solid foo\nendsolid foo\n"),
    ],
)
def test_a_malformed_stl_file_raises_empty_mesh_rather_than_crashing(
    tmp_path: Path, name: str, payload: bytes
) -> None:
    path = tmp_path / "malformed.stl"
    path.write_bytes(payload)

    with pytest.raises(EmptyMeshError):
        render(mesh_render.load_stl(path))


@pytest.mark.parametrize(
    "name, triangles",
    [
        ("one Inf triangle beside one good one", [[(INF, 0, 0), (1, 0, 0), (0, 1, 0)], GOOD]),
        ("sub-micron single triangle", [[(0, 0, 0), (1e-9, 0, 0), (0, 1e-9, 0)]]),
        ("1e9-scale single triangle", [[(0, 0, 0), (1e9, 0, 0), (0, 1e9, 1e9)]]),
        ("extreme sliver aspect ratio", [[(0, 0, 0), (1000, 0.001, 0), (0, 0.001, 0)]]),
        (
            "perfectly flat plate",
            [[(0, 0, 0), (10, 0, 0), (10, 10, 0)], [(0, 0, 0), (10, 10, 0), (0, 10, 0)]],
        ),
    ],
)
def test_extreme_but_renderable_geometry_still_produces_an_image(
    tmp_path: Path, name: str, triangles
) -> None:
    path = binary_stl(tmp_path / "extreme.stl", triangles)

    image = render(mesh_render.load_stl(path))

    assert image.size == (128, 128)
    assert image.mode == "RGBA"
    assert image.getextrema()[3][1] == 255  # something was actually drawn


def test_an_empty_or_single_triangle_array_hits_both_ends_of_the_contract() -> None:
    with pytest.raises(EmptyMeshError):
        render(np.zeros((0, 3, 3), np.float32))

    assert render(np.array([GOOD], np.float32)).size == (128, 128)


def test_render_file_reports_a_missing_path_and_an_unsupported_extension(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        mesh_render.render_file(tmp_path / "absent.stl")

    with pytest.raises(ValueError, match="unsupported extension"):
        mesh_render.render_file(tmp_path / "part.iam")


def test_an_ascii_stl_is_parsed_when_the_size_arithmetic_rules_out_binary(tmp_path: Path) -> None:
    path = tmp_path / "ascii.stl"
    path.write_text(
        "solid cube\n"
        "  facet normal 0 0 1\n"
        "    outer loop\n"
        "      vertex 0 0 0\n"
        "      vertex 10 0 0\n"
        "      vertex 0 10 0\n"
        "    endloop\n"
        "  endfacet\n"
        "endsolid cube\n",
        encoding="ascii",
    )

    triangles = mesh_render.load_stl(path)

    assert triangles.shape == (1, 3, 3)
    assert render(triangles).size == (128, 128)


@pytest.mark.parametrize("stem, staged", [("ボロン探針", True), ("boron_probe", False)])
def test_a_non_ascii_step_path_is_staged_through_an_ascii_temp_file(
    monkeypatch, tmp_path: Path, stem: str, staged: bool
) -> None:
    """OpenCascade's file IO cannot open a non-ASCII path; this workspace has some."""

    cascadio = pytest.importorskip("cascadio")
    source = tmp_path / f"{stem}.step"
    source.write_bytes(b"ISO-10303-21;\nENDSEC;\nEND-ISO-10303-21;\n")
    handed: dict[str, str] = {}

    def fake_step_to_glb(src, dst, **_kwargs):
        handed["src"] = src
        Path(dst).write_bytes(b"glTF stub")

    monkeypatch.setattr(cascadio, "step_to_glb", fake_step_to_glb)
    monkeypatch.setattr(mesh_render, "load_trimesh", lambda _path: np.zeros((0, 3, 3), np.float32))

    mesh_render.load_step(source)

    assert handed["src"].isascii()
    assert (Path(handed["src"]).name == "input.step") is staged
    assert (handed["src"] == str(source)) is not staged


def test_a_missing_step_file_raises_before_any_temp_directory_is_made(tmp_path: Path) -> None:
    pytest.importorskip("cascadio")

    with pytest.raises(FileNotFoundError):
        mesh_render.load_step(tmp_path / "absent.step")


def test_a_binary_stl_wearing_an_ascii_header_is_still_read_as_binary(tmp_path: Path) -> None:
    """The 80-byte header is free text; only the size arithmetic is reliable."""

    path = tmp_path / "liar.stl"
    header = b"solid exported_by_something".ljust(80, b"\0")
    body = struct.pack("<I", 1) + struct.pack("<3f", 0, 0, 1)
    for vertex in GOOD:
        body += struct.pack("<3f", *vertex)
    path.write_bytes(header + body + b"\0\0")

    assert mesh_render._looks_binary_stl(path.read_bytes()) is True
    assert mesh_render.load_stl(path).shape == (1, 3, 3)
