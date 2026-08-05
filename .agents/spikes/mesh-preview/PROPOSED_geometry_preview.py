"""
PROPOSED production module -- would live at src/pihti_dedup/geometry_preview.py

This is a SKETCH for review, not applied to the repo. It shows the shape that
fits the existing codebase:

  * returns the existing `Preview` dataclass from inventor_meta, so
    web.preview_image needs no change to its response handling
  * adds a disk cache under .pihti-dedup/ (already gitignored), because
    STEP rendering costs seconds and the current cache is in-memory only
  * degrades to the existing placeholder_svg when an optional dep is absent

Integration points in the existing code:
  web.py:103-128   PreviewCache.get   -- gate currently limits to INVENTOR_EXTENSIONS
  web.py:453-464   preview_image      -- unchanged
  web.py:131-145   placeholder_svg    -- unchanged fallback
  inventory.py:18  CAD_EXTENSIONS     -- already lists .stl/.step/.stp/.dwg
"""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# Bump whenever the renderer's visual output changes; it is part of the cache
# key so old PNGs are superseded rather than served stale.
RENDERER_VERSION = 1

MESH_EXTENSIONS = frozenset({".stl", ".3mf"})
STEP_EXTENSIONS = frozenset({".stp", ".step"})
DRAWING_EXTENSIONS = frozenset({".dwg"})

# What this module can attempt at all. STEP is included only when the optional
# dependency is importable -- see `available_extensions()`.
GEOMETRY_EXTENSIONS = MESH_EXTENSIONS | STEP_EXTENSIONS | DRAWING_EXTENSIONS

PREVIEW_SIZE = 512


def _has_cascadio() -> bool:
    try:
        import cascadio  # noqa: F401
    except ImportError:
        return False
    return True


def available_extensions() -> frozenset[str]:
    """Extensions this install can actually render, given optional deps.

    .stl and .dwg need nothing beyond numpy/Pillow (Pillow is already a
    transitive need for nothing today, so it becomes a hard dep of the
    `preview` extra). .stp/.step additionally need cascadio + trimesh.
    """
    exts = set(MESH_EXTENSIONS | DRAWING_EXTENSIONS)
    if _has_cascadio():
        exts |= STEP_EXTENSIONS
    return frozenset(exts)


def cache_key(path: Path, mtime_ns: int, size: int = PREVIEW_SIZE) -> str:
    """Stable per-file key.

    Mirrors the in-memory PreviewCache key (normcased path + mtime_ns) and
    adds the render size and renderer version so a style change or a resize
    invalidates cleanly. st_size is folded in as a cheap guard against
    mtime collisions after a restore/copy.
    """
    import os

    raw = "\0".join(
        [
            os.path.normcase(str(path.resolve())),
            str(mtime_ns),
            str(path.stat().st_size),
            str(size),
            str(RENDERER_VERSION),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_path(workspace: Path, key: str) -> Path:
    # shard by first two hex chars to keep directory sizes sane
    return workspace / ".pihti-dedup" / "previews" / key[:2] / f"{key}.png"


@dataclass(frozen=True)
class Preview:  # mirrors inventor_meta.Preview -- import that one in real code
    data: bytes
    image_format: str

    @property
    def media_type(self) -> str:
        return {"png": "image/png"}[self.image_format]


def render(path: Path, *, size: int = PREVIEW_SIZE) -> Preview | None:
    """Render one geometry file to a PNG Preview, or None if not possible.

    Never raises for bad input: a corrupt or empty mesh returns None so the
    caller falls through to placeholder_svg, exactly like a missing Inventor
    thumbnail does today.
    """
    suffix = path.suffix.casefold()
    try:
        if suffix in DRAWING_EXTENSIONS:
            from . import dwg_preview

            img, _kind = dwg_preview.render_preview(path, size=size)
            if img is None:
                return None
        else:
            from . import mesh_render

            if suffix in MESH_EXTENSIONS:
                tris = mesh_render.load_stl(path)
            elif suffix in STEP_EXTENSIONS:
                if not _has_cascadio():
                    return None
                tris = mesh_render.load_step(path)
            else:
                return None
            img = mesh_render.render_triangles(tris, size=size, ssaa=2)
    except FileNotFoundError:
        return None
    except Exception:  # corrupt geometry must not take down a page render
        log.warning("preview render failed for %s", path, exc_info=True)
        return None

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return Preview(data=buf.getvalue(), image_format="png")


def get_or_render(workspace: Path, path: Path, mtime_ns: int,
                  *, size: int = PREVIEW_SIZE) -> Preview | None:
    """Disk-cached render. Safe to call from multiple threads/processes."""
    key = cache_key(path, mtime_ns, size)
    dest = cache_path(workspace, key)

    if dest.exists():
        try:
            return Preview(data=dest.read_bytes(), image_format="png")
        except OSError:
            pass

    preview = render(path, size=size)
    if preview is None:
        return None

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # write to a unique temp name then replace, so a concurrent reader
        # never observes a half-written PNG
        tmp = dest.with_suffix(f".{id(preview):x}.tmp")
        tmp.write_bytes(preview.data)
        tmp.replace(dest)
    except OSError:
        log.warning("could not cache preview for %s", path, exc_info=True)
    return preview
