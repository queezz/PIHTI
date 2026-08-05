"""
meshpreview -- numpy software renderer for mesh previews (STL / STEP-via-cascadio).

Produces 512x512 RGBA PNGs in a style sympathetic to Inventor embedded thumbnails:
light neutral part, flat-shaded from a single key light plus ambient fill,
orthographic isometric-ish camera, transparent background.

No GPU, no OpenGL, no system deps beyond numpy + Pillow.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


class EmptyMeshError(ValueError):
    """Raised when a file parses fine but contains no renderable geometry."""


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

_VERTEX_RE = re.compile(
    rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", re.IGNORECASE
)


def _looks_binary_stl(buf: bytes) -> bool:
    """Binary STL is authoritative if the triangle count matches the file size.

    Some exporters write an ASCII-looking 'solid ...' header on binary files
    and vice versa, so the size arithmetic is the only reliable test.
    """
    if len(buf) < 84:
        return False
    (n_tri,) = struct.unpack_from("<I", buf, 80)
    return len(buf) == 84 + n_tri * 50


def load_stl(path) -> np.ndarray:
    """Return an (N, 3, 3) float32 array of triangle vertices."""
    buf = Path(path).read_bytes()

    if _looks_binary_stl(buf):
        (n_tri,) = struct.unpack_from("<I", buf, 80)
        if n_tri == 0:
            return np.zeros((0, 3, 3), dtype=np.float32)
        raw = np.frombuffer(buf, dtype=np.uint8, offset=84, count=n_tri * 50)
        raw = raw.reshape(n_tri, 50)
        # bytes 0:48 are 12 float32 (normal xyz + 3 * vertex xyz); 48:50 is attr
        floats = raw[:, :48].copy().view(np.float32).reshape(n_tri, 12)
        return np.ascontiguousarray(floats[:, 3:12].reshape(n_tri, 3, 3))

    # ASCII fallback
    matches = _VERTEX_RE.findall(buf)
    if not matches:
        return np.zeros((0, 3, 3), dtype=np.float32)
    flat = np.array(matches, dtype=np.bytes_).astype(np.float64)
    n_tri = flat.shape[0] // 3
    if n_tri == 0:
        return np.zeros((0, 3, 3), dtype=np.float32)
    return np.ascontiguousarray(
        flat[: n_tri * 3].reshape(n_tri, 3, 3).astype(np.float32)
    )


def load_glb(path) -> np.ndarray:
    """Load any trimesh-readable file (GLB/GLTF/OBJ/PLY/...) as triangles."""
    import trimesh

    scene = trimesh.load(str(path), force="scene")

    parts = []
    for name, geom in scene.geometry.items():
        if not hasattr(geom, "triangles"):
            continue
        tris = np.asarray(geom.triangles, dtype=np.float64)
        if not tris.size:
            continue
        # place the geometry using its scene-graph transform, otherwise every
        # instanced part renders stacked at the origin
        try:
            node = scene.graph.geometry_nodes[name][0]
            xf, _ = scene.graph.get(node)
            pts = tris.reshape(-1, 3) @ xf[:3, :3].T + xf[:3, 3]
            tris = pts.reshape(-1, 3, 3)
        except Exception:
            pass
        parts.append(tris.astype(np.float32))

    if not parts:
        return np.zeros((0, 3, 3), dtype=np.float32)
    return np.ascontiguousarray(np.concatenate(parts, axis=0))


def load_step(path) -> np.ndarray:
    """Tessellate a STEP file via cascadio (OpenCascade) and return triangles.

    OpenCascade's file IO cannot open non-ASCII paths on Windows, and this
    repo has STEP files with Japanese names, so the source is staged through
    an ASCII-only temp path whenever the original is not pure ASCII.
    """
    import shutil
    import tempfile

    import cascadio

    src = Path(path)
    work = Path(tempfile.mkdtemp(prefix="steppreview-"))
    try:
        stage = src
        if not str(src).isascii():
            stage = work / ("input" + src.suffix.lower())
            shutil.copyfile(src, stage)

        glb = work / "out.glb"
        # tol_linear/tol_angular drive tessellation density; these are a
        # preview-grade compromise between fidelity and time.
        cascadio.step_to_glb(
            str(stage), str(glb), tol_linear=0.1, tol_angular=0.5
        )
        if not glb.exists():
            raise RuntimeError("cascadio produced no output")
        return load_glb(glb)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


@dataclass
class Style:
    """Look-and-feel knobs for the rendered preview."""

    base_color: tuple = (203, 208, 214)   # light neutral steel
    ambient: float = 0.42
    key_light: tuple = (-0.35, -0.55, 0.75)  # from upper-left, toward viewer
    fill_strength: float = 0.18
    background: tuple | None = None       # None => transparent
    margin: float = 0.06                  # fraction of frame left as padding


ISO_EYE = (1.0, -1.0, 0.72)   # front / right / above, Z-up (Inventor-ish home)
UP = (0.0, 0.0, 1.0)


def _camera_basis(eye_dir=ISO_EYE, up=UP):
    eye = np.asarray(eye_dir, dtype=np.float64)
    eye /= np.linalg.norm(eye)
    fwd = -eye                                    # eye -> target
    upv = np.asarray(up, dtype=np.float64)
    right = np.cross(fwd, upv)
    nr = np.linalg.norm(right)
    if nr < 1e-9:                                 # looking straight down
        right = np.array([1.0, 0.0, 0.0])
    else:
        right /= nr
    true_up = np.cross(right, fwd)
    true_up /= np.linalg.norm(true_up)
    return right, true_up, fwd


def _clean(tris: np.ndarray) -> np.ndarray:
    """Drop non-finite and zero-area triangles."""
    if tris.shape[0] == 0:
        return tris
    finite = np.isfinite(tris).all(axis=(1, 2))
    tris = tris[finite]
    if tris.shape[0] == 0:
        return tris
    e1 = tris[:, 1] - tris[:, 0]
    e2 = tris[:, 2] - tris[:, 0]
    n = np.cross(e1, e2)
    area2 = np.linalg.norm(n, axis=1)
    scale = max(float(np.abs(tris).max()), 1e-12)
    return tris[area2 > (1e-12 * scale * scale)]


def _quantize_extent(extent: np.ndarray, cap: int) -> np.ndarray:
    """Round each screen-bbox dimension up onto a ~1/8-per-octave ladder.

    Rounding up to a power of two would overshoot by up to 2x per axis (4x in
    area), and the render cost is dominated by the few triangles with large
    screen bounding boxes, so that waste is exactly where it hurts. This keeps
    the same "few distinct window sizes" property with ~12% overshoot instead.
    """
    e = np.maximum(extent, 1).astype(np.int64)
    octave = np.floor(np.log2(e.astype(np.float64))).astype(np.int64)
    step = np.maximum(1, np.left_shift(1, np.maximum(0, octave - 3)))
    q = ((e + step - 1) // step) * step
    return np.minimum(q, cap).astype(np.int32)


def render_triangles(
    tris: np.ndarray,
    size: int = 512,
    ssaa: int = 2,
    style: Style | None = None,
    eye_dir=ISO_EYE,
) -> Image.Image:
    """Rasterize triangles to a PIL RGBA image with a z-buffer + flat shading."""
    style = style or Style()
    tris = _clean(np.asarray(tris, dtype=np.float32))
    if tris.shape[0] == 0:
        raise EmptyMeshError("no renderable triangles")

    res = size * ssaa
    right, up, fwd = _camera_basis(eye_dir)

    # ---- project to camera space (orthographic) ------------------------
    pts = tris.reshape(-1, 3).astype(np.float64)
    centre = 0.5 * (pts.min(axis=0) + pts.max(axis=0))
    pts -= centre

    cam = np.empty_like(pts)
    cam[:, 0] = pts @ right
    cam[:, 1] = pts @ up
    cam[:, 2] = pts @ fwd            # depth, larger == farther
    cam = cam.reshape(-1, 3, 3)

    # ---- fit to frame --------------------------------------------------
    lo = cam[:, :, :2].reshape(-1, 2).min(axis=0)
    hi = cam[:, :, :2].reshape(-1, 2).max(axis=0)
    span = float(np.max(hi - lo))
    if span <= 0:
        raise EmptyMeshError("degenerate bounding box")
    usable = res * (1.0 - 2.0 * style.margin)
    scale = usable / span
    mid = 0.5 * (lo + hi)

    sx = (cam[:, :, 0] - mid[0]) * scale + res * 0.5
    sy = res * 0.5 - (cam[:, :, 1] - mid[1]) * scale   # flip: screen Y down
    sz = cam[:, :, 2]

    # ---- shading (flat, per triangle, from world-space normals) --------
    e1 = tris[:, 1].astype(np.float64) - tris[:, 0]
    e2 = tris[:, 2].astype(np.float64) - tris[:, 0]
    nrm = np.cross(e1, e2)
    nlen = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm /= np.maximum(nlen, 1e-30)

    # two-sided: flip normals that face away from the camera
    facing = nrm @ (-fwd)
    nrm[facing < 0] *= -1.0
    facing = np.abs(facing)

    key = np.asarray(style.key_light, dtype=np.float64)
    key /= np.linalg.norm(key)
    # express the key light in camera space so it tracks the view
    key_world = key[0] * right + key[1] * fwd + key[2] * up
    key_world /= np.linalg.norm(key_world)

    lam = np.clip(nrm @ key_world, 0.0, 1.0)
    inten = style.ambient + (1.0 - style.ambient) * lam
    inten += style.fill_strength * facing          # gentle view-dependent fill
    np.clip(inten, 0.0, 1.15, out=inten)

    base = np.asarray(style.base_color, dtype=np.float64)
    tri_rgb = np.clip(inten[:, None] * base[None, :], 0, 255).astype(np.uint8)

    # ---- rasterize -----------------------------------------------------
    tri_idx = _rasterize(sx, sy, sz, res)

    out = np.zeros((res, res, 4), dtype=np.uint8)
    hit = tri_idx >= 0
    if not hit.any():
        raise EmptyMeshError("nothing projected into frame")
    out[hit, :3] = tri_rgb[tri_idx[hit]]
    out[hit, 3] = 255

    img = Image.fromarray(out, mode="RGBA")
    if ssaa != 1:
        img = img.resize((size, size), Image.LANCZOS)

    if style.background is not None:
        bg = Image.new("RGBA", img.size, tuple(style.background) + (255,))
        img = Image.alpha_composite(bg, img)
    return img


def _scatter(zbuf, frag_pix, frag_z, frag_tri, zmin, zrange, z_max, idx_bits):
    """Merge fragments into the packed z-buffer, nearest wins."""
    qz = np.clip(((frag_z - zmin) / zrange) * z_max, 0, z_max).astype(np.uint64)
    packed = (qz << np.uint64(idx_bits)) | frag_tri

    # Reduce to one winning fragment per pixel before touching the z-buffer.
    # Scattering with duplicate indices has unspecified ordering in numpy,
    # so dedupe first and keep the scatter unique.
    order = np.lexsort((packed, frag_pix))
    uniq_pix, first = np.unique(frag_pix[order], return_index=True)
    best = packed[order][first]
    zbuf[uniq_pix] = np.minimum(zbuf[uniq_pix], best)


def _rasterize(sx, sy, sz, res, chunk_frags=6_000_000):
    """Z-buffered triangle rasterizer, vectorized by screen-bbox size bucket.

    Triangles are grouped by the power-of-two size of their screen bounding
    box, so a whole group can be tested against one fixed offset window at
    once. Depth resolution is handled by packing quantized z and the triangle
    index into a single uint64, sorting descending, and letting plain fancy
    indexing perform "nearest wins".

    Returns an (res, res) int32 array of triangle indices, -1 where empty.
    """
    n = sx.shape[0]

    x0 = np.floor(sx.min(axis=1)).astype(np.int32)
    x1 = np.ceil(sx.max(axis=1)).astype(np.int32)
    y0 = np.floor(sy.min(axis=1)).astype(np.int32)
    y1 = np.ceil(sy.max(axis=1)).astype(np.int32)

    np.clip(x0, 0, res - 1, out=x0)
    np.clip(y0, 0, res - 1, out=y0)
    np.clip(x1, 0, res - 1, out=x1)
    np.clip(y1, 0, res - 1, out=y1)

    w = (x1 - x0 + 1).astype(np.int32)
    h = (y1 - y0 + 1).astype(np.int32)
    onscreen = (w > 0) & (h > 0)

    # Bucket each axis independently. Using a square max(w,h) window instead
    # would cost up to 256x extra on long thin triangles, which dominate
    # low-poly CAD exports (a 1000x3 px sliver would get a 1024x1024 window).
    qw = _quantize_extent(w, res)
    qh = _quantize_extent(h, res)
    bucket_key = qw.astype(np.int64) * (res + 1) + qh

    # Depth packing: 39 bits of quantized z above 24 bits of triangle index.
    # Keeping the total at 63 bits leaves bit 63 free for the empty sentinel,
    # so every real fragment compares strictly less than an untouched pixel.
    zmin, zmax = float(sz.min()), float(sz.max())
    zrange = zmax - zmin
    if zrange <= 0:
        zrange = 1.0
    Z_BITS = 39
    Z_MAX = (1 << Z_BITS) - 1
    IDX_BITS = 24
    SENTINEL = np.uint64(1) << np.uint64(63)

    if n >= (1 << IDX_BITS):
        raise ValueError(f"too many triangles for the index packing: {n}")

    zbuf = np.full(res * res, SENTINEL, dtype=np.uint64)

    # Force a consistent winding so every edge function is positive inside.
    # That removes the per-fragment divisions from the coverage test.
    ax, ay = sx[:, 0].astype(np.float32), sy[:, 0].astype(np.float32)
    bx, by = sx[:, 1].astype(np.float32), sy[:, 1].astype(np.float32)
    cx, cy = sx[:, 2].astype(np.float32), sy[:, 2].astype(np.float32)
    za, zb, zc = (sz[:, i].astype(np.float32) for i in range(3))

    area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    flip = area < 0
    if flip.any():
        bx[flip], cx[flip] = cx[flip], bx[flip].copy()
        by[flip], cy[flip] = cy[flip], by[flip].copy()
        zb[flip], zc[flip] = zc[flip], zb[flip].copy()
        area[flip] = -area[flip]

    for key in np.unique(bucket_key):
        sel = np.nonzero(onscreen & (bucket_key == key) & (area > 1e-9))[0]
        if sel.size == 0:
            continue

        bw = int(key // (res + 1))
        bh = int(key % (res + 1))
        px = bw * bh
        per_chunk = max(1, chunk_frags // px)

        oy, ox = np.divmod(np.arange(px, dtype=np.int32), bw)

        for start in range(0, sel.size, per_chunk):
            g = sel[start : start + per_chunk]

            gx = x0[g][:, None] + ox[None, :]      # (m, px)
            gy = y0[g][:, None] + oy[None, :]

            valid = (gx <= x1[g][:, None]) & (gy <= y1[g][:, None])

            # pixel centres
            fx = gx.astype(np.float32) + np.float32(0.5)
            fy = gy.astype(np.float32) + np.float32(0.5)

            gax, gay = ax[g][:, None], ay[g][:, None]
            gbx, gby = bx[g][:, None], by[g][:, None]
            gcx, gcy = cx[g][:, None], cy[g][:, None]

            # unnormalized edge functions; all >= 0 exactly inside the triangle
            e0 = (gbx - gax) * (fy - gay) - (gby - gay) * (fx - gax)   # -> C
            e1 = (gcx - gbx) * (fy - gby) - (gcy - gby) * (fx - gbx)   # -> A
            e2 = (gax - gcx) * (fy - gcy) - (gay - gcy) * (fx - gcx)   # -> B
            inside = (e0 >= 0) & (e1 >= 0) & (e2 >= 0) & valid

            ii = np.nonzero(inside)
            if ii[0].size == 0:
                continue

            # interpolate depth only on covered fragments
            inv_area = (1.0 / area[g])[ii[0]]
            frag_z = (
                e0[ii] * zc[g][ii[0]]
                + e1[ii] * za[g][ii[0]]
                + e2[ii] * zb[g][ii[0]]
            ) * inv_area

            frag_pix = (gy[ii].astype(np.int64) * res + gx[ii].astype(np.int64))
            frag_tri = g[ii[0]].astype(np.uint64)

            _scatter(zbuf, frag_pix, frag_z, frag_tri, zmin, zrange, Z_MAX, IDX_BITS)

    # Conservative pass: a triangle thinner than a pixel covers no pixel
    # centre and would vanish entirely, which erases genuinely thin features
    # (wire forms, sheet edges, fine ribs). Splatting each triangle's centroid
    # guarantees at least one pixel. The centroid always lies inside the
    # triangle, so this only ever adds coverage the triangle really overlaps.
    cxx = (ax + bx + cx) / 3.0
    cyy = (ay + by + cy) / 3.0
    czz = (za + zb + zc) / 3.0
    px_i = np.floor(cxx).astype(np.int64)
    py_i = np.floor(cyy).astype(np.int64)
    good = (px_i >= 0) & (px_i < res) & (py_i >= 0) & (py_i < res)
    good &= np.isfinite(czz)
    if good.any():
        gi = np.nonzero(good)[0]
        _scatter(
            zbuf,
            py_i[gi] * res + px_i[gi],
            czz[gi],
            gi.astype(np.uint64),
            zmin, zrange, Z_MAX, IDX_BITS,
        )

    filled = zbuf != SENTINEL
    out = np.full(res * res, -1, dtype=np.int32)
    out[filled] = (zbuf[filled] & np.uint64((1 << IDX_BITS) - 1)).astype(np.int32)
    return out.reshape(res, res)


# --------------------------------------------------------------------------
# Front door
# --------------------------------------------------------------------------

def render_file(path, size=512, ssaa=2, style=None) -> Image.Image:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".stl":
        tris = load_stl(p)
    elif ext in (".stp", ".step"):
        tris = load_step(p)
    elif ext in (".glb", ".gltf", ".obj", ".ply", ".3mf"):
        tris = load_glb(p)
    else:
        raise ValueError(f"unsupported extension: {ext}")
    return render_triangles(tris, size=size, ssaa=ssaa, style=style)
