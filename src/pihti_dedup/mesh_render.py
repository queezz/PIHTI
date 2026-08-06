"""A numpy software renderer for mesh previews (STL, STEP via cascadio, 3MF).

An `.stl` or `.step` export carries no embedded thumbnail the way an Inventor
document does, so the catalog showed a grey placeholder for every one of them.
This module renders the geometry instead: a 512×512 RGBA PNG in a style
sympathetic to Inventor's own thumbnails — light neutral part, flat-shaded from
one key light plus ambient fill, orthographic isometric-ish camera, transparent
background. No GPU, no OpenGL, no system libraries beyond numpy and Pillow.

Import this module only behind `geometry_preview.available_extensions()`: numpy
and Pillow are the optional `preview` extra, and an install without them must
degrade to the placeholder rather than fail to import.

Nothing here writes to a CAD file.
"""

from __future__ import annotations

import re
import shutil
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

#: Front / right / above, Z-up — Inventor's home view, near enough.
ISO_EYE = (1.0, -1.0, 0.72)
UP = (0.0, 0.0, 1.0)

_VERTEX_RE = re.compile(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", re.IGNORECASE)


class EmptyMeshError(ValueError):
    """The file parsed but holds no renderable geometry."""


@dataclass(frozen=True)
class Style:
    """Look-and-feel knobs for a rendered preview."""

    base_color: tuple = (203, 208, 214)  # light neutral steel
    ambient: float = 0.42
    key_light: tuple = (-0.35, -0.55, 0.75)  # upper-left, toward the viewer
    fill_strength: float = 0.18
    background: tuple | None = None  # None => transparent
    margin: float = 0.06  # fraction of the frame left as padding


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _looks_binary_stl(buf: bytes) -> bool:
    """Binary STL is authoritative when the triangle count matches the length.

    Some exporters write an ASCII-looking `solid ...` header onto a binary file
    and the reverse, so the size arithmetic is the only reliable test.
    """

    if len(buf) < 84:
        return False
    (n_tri,) = struct.unpack_from("<I", buf, 80)
    return len(buf) == 84 + n_tri * 50


def load_stl(path: Path | str) -> np.ndarray:
    """Return an (N, 3, 3) float32 array of triangle vertices."""

    buf = Path(path).read_bytes()

    if _looks_binary_stl(buf):
        (n_tri,) = struct.unpack_from("<I", buf, 80)
        if n_tri == 0:
            return np.zeros((0, 3, 3), dtype=np.float32)
        raw = np.frombuffer(buf, dtype=np.uint8, offset=84, count=n_tri * 50).reshape(n_tri, 50)
        # bytes 0:48 are 12 float32 (normal xyz then three vertex xyz); 48:50 is attr
        floats = raw[:, :48].copy().view(np.float32).reshape(n_tri, 12)
        return np.ascontiguousarray(floats[:, 3:12].reshape(n_tri, 3, 3))

    matches = _VERTEX_RE.findall(buf)
    if not matches:
        return np.zeros((0, 3, 3), dtype=np.float32)
    flat = np.array(matches, dtype=np.bytes_).astype(np.float64)
    n_tri = flat.shape[0] // 3
    if n_tri == 0:
        return np.zeros((0, 3, 3), dtype=np.float32)
    return np.ascontiguousarray(flat[: n_tri * 3].reshape(n_tri, 3, 3).astype(np.float32))


def load_trimesh(path: Path | str) -> np.ndarray:
    """Load any trimesh-readable file (GLB, 3MF, OBJ, PLY, ...) as triangles."""

    import trimesh

    scene = trimesh.load(str(path), force="scene")

    parts = []
    for name, geom in scene.geometry.items():
        if not hasattr(geom, "triangles"):
            continue
        tris = np.asarray(geom.triangles, dtype=np.float64)
        if not tris.size:
            continue
        # Place the geometry using its scene-graph transform; otherwise every
        # instanced part renders stacked at the origin.
        try:
            node = scene.graph.geometry_nodes[name][0]
            transform, _ = scene.graph.get(node)
            points = tris.reshape(-1, 3) @ transform[:3, :3].T + transform[:3, 3]
            tris = points.reshape(-1, 3, 3)
        except Exception:  # a missing transform is not a reason to lose the mesh
            pass
        parts.append(tris.astype(np.float32))

    if not parts:
        return np.zeros((0, 3, 3), dtype=np.float32)
    return np.ascontiguousarray(np.concatenate(parts, axis=0))


def load_step(path: Path | str) -> np.ndarray:
    """Tessellate a STEP file through cascadio (OpenCascade) and return triangles.

    OpenCascade's file IO cannot open a non-ASCII path on Windows, and this
    workspace has STEP files with Japanese names, so a non-ASCII source is
    staged through an ASCII-only temporary path first. Tolerances stay at
    preview quality: loosening them does not speed the conversion up, because
    the cost is the STEP parser rather than the tessellator.
    """

    import cascadio

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    work = Path(tempfile.mkdtemp(prefix="pihti-step-"))
    try:
        stage = source
        if not str(source).isascii():
            stage = work / ("input" + source.suffix.lower())
            shutil.copyfile(source, stage)
        glb = work / "out.glb"
        cascadio.step_to_glb(str(stage), str(glb), tol_linear=0.1, tol_angular=0.5)
        if not glb.exists():
            raise RuntimeError("cascadio produced no output")
        return load_trimesh(glb)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _camera_basis(eye_dir=ISO_EYE, up=UP):
    eye = np.asarray(eye_dir, dtype=np.float64)
    eye /= np.linalg.norm(eye)
    forward = -eye
    up_vector = np.asarray(up, dtype=np.float64)
    right = np.cross(forward, up_vector)
    length = np.linalg.norm(right)
    if length < 1e-9:  # looking straight down the up axis
        right = np.array([1.0, 0.0, 0.0])
    else:
        right /= length
    true_up = np.cross(right, forward)
    true_up /= np.linalg.norm(true_up)
    return right, true_up, forward


def _clean(tris: np.ndarray) -> np.ndarray:
    """Drop non-finite and zero-area triangles."""

    if tris.shape[0] == 0:
        return tris
    tris = tris[np.isfinite(tris).all(axis=(1, 2))]
    if tris.shape[0] == 0:
        return tris
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    twice_area = np.linalg.norm(normals, axis=1)
    scale = max(float(np.abs(tris).max()), 1e-12)
    return tris[twice_area > (1e-12 * scale * scale)]


def _quantize_extent(extent: np.ndarray, cap: int) -> np.ndarray:
    """Round each screen-bbox dimension up onto a ~1/8-per-octave ladder.

    Rounding up to a power of two would overshoot by up to 2× per axis, 4× in
    area, and render cost is dominated by the few triangles with a large
    screen bounding box — exactly where that waste lands. This keeps the "few
    distinct window sizes" property with about 12% overshoot instead.
    """

    sizes = np.maximum(extent, 1).astype(np.int64)
    octave = np.floor(np.log2(sizes.astype(np.float64))).astype(np.int64)
    step = np.maximum(1, np.left_shift(1, np.maximum(0, octave - 3)))
    return np.minimum(((sizes + step - 1) // step) * step, cap).astype(np.int32)


def render_triangles(
    tris: np.ndarray,
    size: int = 512,
    ssaa: int = 2,
    style: Style | None = None,
    eye_dir=ISO_EYE,
) -> Image.Image:
    """Rasterize triangles to a PIL RGBA image with a z-buffer and flat shading."""

    style = style or Style()
    tris = _clean(np.asarray(tris, dtype=np.float32))
    if tris.shape[0] == 0:
        raise EmptyMeshError("no renderable triangles")

    res = size * ssaa
    right, up, forward = _camera_basis(eye_dir)

    # --- project to camera space (orthographic) ---------------------------
    points = tris.reshape(-1, 3).astype(np.float64)
    points -= 0.5 * (points.min(axis=0) + points.max(axis=0))

    cam = np.empty_like(points)
    cam[:, 0] = points @ right
    cam[:, 1] = points @ up
    cam[:, 2] = points @ forward  # depth, larger is farther
    cam = cam.reshape(-1, 3, 3)

    # --- fit to frame ------------------------------------------------------
    low = cam[:, :, :2].reshape(-1, 2).min(axis=0)
    high = cam[:, :, :2].reshape(-1, 2).max(axis=0)
    span = float(np.max(high - low))
    if span <= 0:
        raise EmptyMeshError("degenerate bounding box")
    scale = (res * (1.0 - 2.0 * style.margin)) / span
    mid = 0.5 * (low + high)

    sx = (cam[:, :, 0] - mid[0]) * scale + res * 0.5
    sy = res * 0.5 - (cam[:, :, 1] - mid[1]) * scale  # flip: screen Y grows down
    sz = cam[:, :, 2]

    # --- flat shading from world-space normals -----------------------------
    normals = np.cross(
        tris[:, 1].astype(np.float64) - tris[:, 0],
        tris[:, 2].astype(np.float64) - tris[:, 0],
    )
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-30)

    facing = normals @ (-forward)
    normals[facing < 0] *= -1.0  # two-sided: flip anything facing away
    facing = np.abs(facing)

    key = np.asarray(style.key_light, dtype=np.float64)
    key /= np.linalg.norm(key)
    key_world = key[0] * right + key[1] * forward + key[2] * up
    key_world /= np.linalg.norm(key_world)

    lambert = np.clip(normals @ key_world, 0.0, 1.0)
    intensity = style.ambient + (1.0 - style.ambient) * lambert
    intensity += style.fill_strength * facing  # gentle view-dependent fill
    np.clip(intensity, 0.0, 1.15, out=intensity)

    base = np.asarray(style.base_color, dtype=np.float64)
    tri_rgb = np.clip(intensity[:, None] * base[None, :], 0, 255).astype(np.uint8)

    # --- rasterize ---------------------------------------------------------
    tri_idx = _rasterize(sx, sy, sz, res)

    out = np.zeros((res, res, 4), dtype=np.uint8)
    hit = tri_idx >= 0
    if not hit.any():
        raise EmptyMeshError("nothing projected into frame")
    out[hit, :3] = tri_rgb[tri_idx[hit]]
    out[hit, 3] = 255

    image = Image.fromarray(out, mode="RGBA")
    if ssaa != 1:
        image = image.resize((size, size), Image.LANCZOS)
    if style.background is not None:
        backdrop = Image.new("RGBA", image.size, tuple(style.background) + (255,))
        image = Image.alpha_composite(backdrop, image)
    return image


def _scatter(zbuf, frag_pix, frag_z, frag_tri, zmin, zrange, z_max, idx_bits) -> None:
    """Merge fragments into the packed z-buffer; nearest wins."""

    quantized = np.clip(((frag_z - zmin) / zrange) * z_max, 0, z_max).astype(np.uint64)
    packed = (quantized << np.uint64(idx_bits)) | frag_tri

    # Reduce to one winning fragment per pixel before touching the z-buffer:
    # scattering with duplicate indices has unspecified ordering in numpy, so
    # dedupe first and keep the scatter unique.
    order = np.lexsort((packed, frag_pix))
    unique_pixels, first = np.unique(frag_pix[order], return_index=True)
    zbuf[unique_pixels] = np.minimum(zbuf[unique_pixels], packed[order][first])


def _rasterize(sx, sy, sz, res, chunk_frags: int = 6_000_000) -> np.ndarray:
    """Z-buffered triangle rasterizer, vectorized by screen-bbox size bucket.

    Triangles are grouped by the quantized size of their screen bounding box so
    a whole group can be tested against one fixed offset window at once. Depth
    resolution is handled by packing quantized z above the triangle index in a
    single uint64, so "nearest wins" is a plain minimum.

    Returns an (res, res) int32 array of triangle indices, -1 where empty.
    """

    n = sx.shape[0]

    x0 = np.clip(np.floor(sx.min(axis=1)).astype(np.int32), 0, res - 1)
    x1 = np.clip(np.ceil(sx.max(axis=1)).astype(np.int32), 0, res - 1)
    y0 = np.clip(np.floor(sy.min(axis=1)).astype(np.int32), 0, res - 1)
    y1 = np.clip(np.ceil(sy.max(axis=1)).astype(np.int32), 0, res - 1)

    width = (x1 - x0 + 1).astype(np.int32)
    height = (y1 - y0 + 1).astype(np.int32)
    onscreen = (width > 0) & (height > 0)

    # Bucket each axis independently. A square max(w, h) window would cost up
    # to 256× extra on the long thin triangles that dominate low-poly CAD
    # exports: a 1000×3 px sliver would be given a 1024×1024 window. Measured
    # on this workspace, per-axis windows took the worst case from 31.7 s to
    # 2.1 s.
    bucket_key = _quantize_extent(width, res).astype(np.int64) * (res + 1) + _quantize_extent(
        height, res
    )

    # Depth packing: 39 bits of quantized z above 24 bits of triangle index.
    # Keeping the total at 63 bits leaves bit 63 free for the empty sentinel,
    # so every real fragment compares strictly less than an untouched pixel.
    zmin, zmax = float(sz.min()), float(sz.max())
    zrange = zmax - zmin or 1.0
    z_bits, idx_bits = 39, 24
    z_max = (1 << z_bits) - 1
    sentinel = np.uint64(1) << np.uint64(63)

    if n >= (1 << idx_bits):
        raise ValueError(f"too many triangles for the index packing: {n}")

    zbuf = np.full(res * res, sentinel, dtype=np.uint64)

    # Force consistent winding so every edge function is positive inside; that
    # removes the per-fragment divisions from the coverage test.
    ax, ay = sx[:, 0].astype(np.float32), sy[:, 0].astype(np.float32)
    bx, by = sx[:, 1].astype(np.float32), sy[:, 1].astype(np.float32)
    cx, cy = sx[:, 2].astype(np.float32), sy[:, 2].astype(np.float32)
    za, zb, zc = (sz[:, index].astype(np.float32) for index in range(3))

    area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    flip = area < 0
    if flip.any():
        bx[flip], cx[flip] = cx[flip], bx[flip].copy()
        by[flip], cy[flip] = cy[flip], by[flip].copy()
        zb[flip], zc[flip] = zc[flip], zb[flip].copy()
        area[flip] = -area[flip]

    for key in np.unique(bucket_key):
        selected = np.nonzero(onscreen & (bucket_key == key) & (area > 1e-9))[0]
        if selected.size == 0:
            continue

        window_w = int(key // (res + 1))
        window_h = int(key % (res + 1))
        pixels = window_w * window_h
        per_chunk = max(1, chunk_frags // pixels)

        offset_y, offset_x = np.divmod(np.arange(pixels, dtype=np.int32), window_w)

        for start in range(0, selected.size, per_chunk):
            group = selected[start : start + per_chunk]

            gx = x0[group][:, None] + offset_x[None, :]
            gy = y0[group][:, None] + offset_y[None, :]
            valid = (gx <= x1[group][:, None]) & (gy <= y1[group][:, None])

            fx = gx.astype(np.float32) + np.float32(0.5)  # pixel centres
            fy = gy.astype(np.float32) + np.float32(0.5)

            gax, gay = ax[group][:, None], ay[group][:, None]
            gbx, gby = bx[group][:, None], by[group][:, None]
            gcx, gcy = cx[group][:, None], cy[group][:, None]

            # Unnormalized edge functions; all >= 0 exactly inside the triangle.
            e0 = (gbx - gax) * (fy - gay) - (gby - gay) * (fx - gax)  # opposite C
            e1 = (gcx - gbx) * (fy - gby) - (gcy - gby) * (fx - gbx)  # opposite A
            e2 = (gax - gcx) * (fy - gcy) - (gay - gcy) * (fx - gcx)  # opposite B
            inside = (e0 >= 0) & (e1 >= 0) & (e2 >= 0) & valid

            covered = np.nonzero(inside)
            if covered[0].size == 0:
                continue

            inverse_area = (1.0 / area[group])[covered[0]]
            frag_z = (
                e0[covered] * zc[group][covered[0]]
                + e1[covered] * za[group][covered[0]]
                + e2[covered] * zb[group][covered[0]]
            ) * inverse_area

            _scatter(
                zbuf,
                gy[covered].astype(np.int64) * res + gx[covered].astype(np.int64),
                frag_z,
                group[covered[0]].astype(np.uint64),
                zmin,
                zrange,
                z_max,
                idx_bits,
            )

    # Conservative pass: a triangle thinner than a pixel covers no pixel centre
    # and would vanish entirely, erasing genuinely thin features — wire forms,
    # sheet edges, fine ribs. Splatting each centroid guarantees one pixel, and
    # a centroid always lies inside its triangle, so this only ever adds
    # coverage the triangle really overlaps.
    centre_x = np.floor((ax + bx + cx) / 3.0).astype(np.int64)
    centre_y = np.floor((ay + by + cy) / 3.0).astype(np.int64)
    centre_z = (za + zb + zc) / 3.0
    good = (
        (centre_x >= 0)
        & (centre_x < res)
        & (centre_y >= 0)
        & (centre_y < res)
        & np.isfinite(centre_z)
    )
    if good.any():
        index = np.nonzero(good)[0]
        _scatter(
            zbuf,
            centre_y[index] * res + centre_x[index],
            centre_z[index],
            index.astype(np.uint64),
            zmin,
            zrange,
            z_max,
            idx_bits,
        )

    filled = zbuf != sentinel
    out = np.full(res * res, -1, dtype=np.int32)
    out[filled] = (zbuf[filled] & np.uint64((1 << idx_bits) - 1)).astype(np.int32)
    return out.reshape(res, res)


def render_file(
    path: Path | str, size: int = 512, ssaa: int = 2, style: Style | None = None
) -> Image.Image:
    """Load and render one mesh-bearing file. Raises on anything unrenderable."""

    target = Path(path)
    suffix = target.suffix.casefold()
    if suffix == ".stl":
        tris = load_stl(target)
    elif suffix in (".stp", ".step"):
        tris = load_step(target)
    elif suffix in (".glb", ".gltf", ".obj", ".ply", ".3mf"):
        tris = load_trimesh(target)
    else:
        raise ValueError(f"unsupported extension: {suffix}")
    return render_triangles(tris, size=size, ssaa=ssaa, style=style)
