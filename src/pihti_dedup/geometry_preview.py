"""Previews for the CAD files Inventor did not embed a thumbnail into.

An `.ipt` carries its own preview image and `inventor_meta.read_preview` lifts
it out. An `.stl`, `.step`, `.3mf`, or `.dwg` does not, so the catalog showed a
grey placeholder for roughly 280 files in this workspace. This module is the
front door that fills them in:

- `.stl` and `.3mf` and `.stp`/`.step` are rendered by `mesh_render`
- `.dwg` reuses the preview AutoCAD already embedded, via `dwg_preview`

Three rules the rest of the code depends on:

1. **`render()` returns `inventor_meta.Preview` and never raises.** A corrupt
   mesh, a missing optional dependency, or an unreadable file returns None and
   the caller falls through to `web.placeholder_svg`, exactly as a missing
   Inventor thumbnail does today.
2. **Optional dependencies are probed, never imported at module scope.** numpy
   and Pillow are the `preview` extra; cascadio and trimesh are the `step`
   extra. An install without them degrades to placeholders rather than failing
   to import, so `available_extensions()` is the single truth about what this
   install can draw.
3. **Rendering is disk-cached.** A STEP file costs seconds — median 1.05 s and
   up to 6.99 s measured on this workspace — so a catalog visit must never pay
   for it twice. The cache lives under the gitignored `.pihti-dedup/previews/`,
   sharded by the first two hex characters of the key, written temp-then-replace
   so a concurrent reader never sees a half-written PNG.

Only misses are recomputed: the cache stores successes only. A negative entry
would outlive the reason for it — installing the `step` extra would not
invalidate a "STEP cannot be rendered" marker — and `web.PreviewCache` already
remembers misses for the life of the process.

Nothing here writes to a CAD file.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path

from pihti_dedup.inventor_meta import INVENTOR_EXTENSIONS, Preview

log = logging.getLogger(__name__)

#: Bump when the renderer's visual output changes. It is part of the cache key,
#: so a style change supersedes every stored PNG instead of serving it stale.
RENDERER_VERSION = 1

PREVIEW_SIZE = 512

MESH_EXTENSIONS = frozenset({".stl"})
#: Readable through trimesh alone, which ships with the `step` extra.
TRIMESH_EXTENSIONS = frozenset({".3mf"})
STEP_EXTENSIONS = frozenset({".stp", ".step"})
DRAWING_EXTENSIONS = frozenset({".dwg"})

#: Everything this module knows how to draw, given every optional dependency.
GEOMETRY_EXTENSIONS = MESH_EXTENSIONS | TRIMESH_EXTENSIONS | STEP_EXTENSIONS | DRAWING_EXTENSIONS

CACHE_DIRNAME = "previews"
CACHE_ROOT = ".pihti-dedup"


@dataclass(frozen=True)
class WarmResult:
    """Counts and timing from a whole-workspace preview warm."""

    considered: int = 0
    rendered: int = 0
    cached: int = 0
    failed: int = 0
    seconds: float = 0.0
    failures: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "considered": self.considered,
            "rendered": self.rendered,
            "cached": self.cached,
            "failed": self.failed,
            "seconds": round(self.seconds, 2),
            "failures": list(self.failures),
        }


@lru_cache(maxsize=None)
def _installed(module: str) -> bool:
    """True when a module can be imported, without importing it."""

    try:
        return find_spec(module) is not None
    except (ImportError, ValueError):
        return False


@lru_cache(maxsize=1)
def available_extensions() -> frozenset[str]:
    """Extensions this install can actually draw, given the optional extras.

    `.dwg` only unpacks an image Pillow can decode. `.stl` additionally needs
    numpy for the rasterizer. `.3mf` needs trimesh, and `.stp`/`.step` need
    cascadio on top of it.
    """

    if not _installed("PIL"):
        return frozenset()
    extensions = set(DRAWING_EXTENSIONS)
    if _installed("numpy"):
        extensions |= MESH_EXTENSIONS
        if _installed("trimesh"):
            if _installed("cascadio"):
                extensions |= STEP_EXTENSIONS
            # trimesh defers its 3MF loader to networkx and lxml and raises
            # `ModuleNotFoundError` from the loader rather than at import, so
            # probe for them here instead of discovering it per file.
            if _installed("networkx") and _installed("lxml"):
                extensions |= TRIMESH_EXTENSIONS
    return frozenset(extensions)


def missing_extra() -> str | None:
    """Which optional extra to install for fuller coverage, or None if complete."""

    if not _installed("PIL") or not _installed("numpy"):
        return "preview"
    if not all(_installed(name) for name in ("trimesh", "cascadio", "networkx", "lxml")):
        return "step"
    return None


def previewable_extensions() -> frozenset[str]:
    """Every extension the viewer can show an image for on this install.

    Inventor's embedded thumbnails need nothing installed, so they are always
    in the set; the geometry formats join it as their extras appear.
    """

    return INVENTOR_EXTENSIONS | available_extensions()


def preview_source(suffix: str) -> str:
    """Where a preview for this extension comes from, for the UI to say so."""

    normalized = suffix.casefold()
    if normalized in INVENTOR_EXTENSIONS:
        return "Inventor's embedded thumbnail"
    if normalized in DRAWING_EXTENSIONS:
        return "the DWG's embedded preview"
    if normalized in GEOMETRY_EXTENSIONS:
        return "rendered from the geometry"
    return ""


def preview_store(workspace: Path | str) -> Path:
    """The gitignored directory holding cached preview PNGs."""

    return Path(workspace) / CACHE_ROOT / CACHE_DIRNAME


def cache_key(path: Path, mtime_ns: int, st_size: int, size: int = PREVIEW_SIZE) -> str:
    """Stable per-file key.

    Mirrors the in-memory `web.PreviewCache` key — normcased path plus
    `mtime_ns` — and adds `st_size` as a cheap guard against an mtime collision
    after a restore or copy, the render size, and `RENDERER_VERSION`.
    """

    raw = "\0".join(
        [
            os.path.normcase(str(path)),
            str(mtime_ns),
            str(st_size),
            str(size),
            str(RENDERER_VERSION),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_path(store: Path | str, key: str) -> Path:
    """Shard by the first two hex characters, so no directory holds thousands."""

    return Path(store) / key[:2] / f"{key}.png"


def render(path: Path | str, *, size: int = PREVIEW_SIZE) -> Preview | None:
    """Render one geometry file to a PNG `Preview`, or None if it cannot be.

    Never raises: corrupt geometry must not take down a page render.
    """

    target = Path(path)
    suffix = target.suffix.casefold()
    if suffix not in available_extensions():
        return None
    try:
        if suffix in DRAWING_EXTENSIONS:
            from pihti_dedup import dwg_preview

            image, _kind = dwg_preview.render_preview(target, size=size)
            if image is None:
                return None
        else:
            from pihti_dedup import mesh_render

            if suffix in MESH_EXTENSIONS:
                triangles = mesh_render.load_stl(target)
            elif suffix in STEP_EXTENSIONS:
                triangles = mesh_render.load_step(target)
            elif suffix in TRIMESH_EXTENSIONS:
                triangles = mesh_render.load_trimesh(target)
            else:
                return None
            image = mesh_render.render_triangles(triangles, size=size, ssaa=2)
    except FileNotFoundError:
        return None
    except Exception:  # any parse or render failure falls back to the placeholder
        log.warning("preview render failed for %s", target, exc_info=True)
        return None

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return Preview(data=buffer.getvalue(), image_format="png")


def read_cached(store: Path | str, key: str) -> Preview | None:
    """Return a stored PNG for this key, or None when it is not on disk."""

    destination = cache_path(store, key)
    try:
        return Preview(data=destination.read_bytes(), image_format="png")
    except OSError:
        return None


def write_cached(store: Path | str, key: str, preview: Preview) -> bool:
    """Store a rendered PNG, temp-then-replace. False when the write failed."""

    destination = cache_path(store, key)
    temporary = destination.with_name(f"{destination.name}.{os.getpid():x}.{id(preview):x}.tmp")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(preview.data)
        temporary.replace(destination)
    except OSError:
        log.warning("could not cache a preview at %s", destination, exc_info=True)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def get_or_render(
    workspace: Path | str,
    path: Path | str,
    mtime_ns: int,
    *,
    size: int = PREVIEW_SIZE,
    st_size: int | None = None,
) -> Preview | None:
    """Disk-cached render. Safe to call from several threads or processes."""

    target = Path(path)
    if st_size is None:
        try:
            st_size = target.stat().st_size
        except OSError:
            return None
    store = preview_store(workspace)
    key = cache_key(target, mtime_ns, st_size, size)

    cached = read_cached(store, key)
    if cached is not None:
        return cached

    preview = render(target, size=size)
    if preview is None:
        return None
    write_cached(store, key, preview)
    return preview


def warm_previews(
    workspace: Path | str,
    *,
    include_vendor: bool = False,
    size: int = PREVIEW_SIZE,
    progress=None,
) -> WarmResult:
    """Build every missing geometry preview for a workspace, once.

    A cold whole-repo build costs about 218 s here, which is why this exists as
    a command instead of letting a catalog visit trigger 280 renders.
    """

    from pihti_dedup.inventory import scan_workspace

    root = Path(workspace).resolve()
    store = preview_store(root)
    drawable = available_extensions()
    inventory = scan_workspace(root, include_vendor=include_vendor, hash_files=False)
    targets = [
        record for record in inventory.records if Path(record.path).suffix.casefold() in drawable
    ]

    rendered = cached = failed = 0
    failures: list[str] = []
    started = time.perf_counter()
    for index, record in enumerate(targets, start=1):
        target = root / record.path
        try:
            stat = target.stat()
        except OSError as exc:
            failed += 1
            failures.append(f"{record.path}: {exc}")
            continue
        key = cache_key(target, stat.st_mtime_ns, stat.st_size, size)
        began = time.perf_counter()
        if read_cached(store, key) is not None:
            cached += 1
            state = "cached"
        else:
            preview = render(target, size=size)
            if preview is None:
                failed += 1
                failures.append(f"{record.path}: no preview could be rendered")
                state = "failed"
            else:
                write_cached(store, key, preview)
                rendered += 1
                state = "rendered"
        if progress is not None:
            progress(index, len(targets), record.path, state, time.perf_counter() - began)

    return WarmResult(
        considered=len(targets),
        rendered=rendered,
        cached=cached,
        failed=failed,
        seconds=time.perf_counter() - started,
        failures=tuple(failures),
    )
