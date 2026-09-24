"""Triangle meshes for the inspector's 3D view of STL, 3MF, and STEP files.

The still preview (`geometry_preview`) and this module load geometry through
one function, `geometry_preview.load_triangles`, so the picture and the model
the reader turns in the inspector are the same triangles. What the browser
receives is a compact little-endian binary it can hand to WebGL as is:

- 12 bytes: `PIHTIMESH` padded with zero bytes
- uint32 format version (`MESH_FORMAT_VERSION`)
- uint32 triangle count N
- 6 float32: bounding box min x, y, z, then max x, y, z
- 9N float32 positions, three vertices per triangle
- 9N float32 normals, the triangle's face normal repeated per vertex

The header is 44 bytes, a multiple of four, so both float blocks can be viewed
as `Float32Array`s without a copy.

Three rules, mirroring `geometry_preview`:

1. **Nothing imports numpy at module scope.** A mesh is built only for an
   extension `geometry_preview.available_extensions()` lists; without the
   extra, `build` reports why and the caller answers 404.
2. **Disk-cached, successes only.** A STEP parse costs seconds, so a mesh is
   stored under the gitignored `.pihti-dedup/meshes/`, sharded like previews,
   keyed by path, modification time, size, and the format version, and
   written temp-then-replace. A refusal is not stored: installing an extra or
   raising the cap must not be masked by a stale marker.
3. **A cap, not a stream.** A mesh above `MAX_TRIANGLES` is not served; the
   inspector keeps the still image. At the cap a mesh is about 29 MB.

Nothing here writes to a CAD file.
"""

from __future__ import annotations

import hashlib
import logging
import os
import struct
import time
from dataclasses import dataclass
from pathlib import Path

from pihti_dedup import geometry_preview

log = logging.getLogger(__name__)

#: Bump when the binary layout or the geometry it carries changes.
MESH_FORMAT_VERSION = 1
MAGIC = b"PIHTIMESH\0\0\0"
HEADER = struct.Struct("<12sII6f")

#: Extensions the inspector can turn in 3D, given every optional extra.
MESH_EXTENSIONS = (
    geometry_preview.MESH_EXTENSIONS
    | geometry_preview.TRIMESH_EXTENSIONS
    | geometry_preview.STEP_EXTENSIONS
)

#: Above this the browser would receive tens of megabytes for one hover.
MAX_TRIANGLES = 400_000

CACHE_DIRNAME = "meshes"

TOO_LARGE = "too large for the inspector"
UNREADABLE = "the geometry could not be read"


@dataclass(frozen=True)
class MeshResult:
    """Either the binary mesh or the reason there is none."""

    data: bytes | None = None
    reason: str = ""
    triangles: int = 0


def eligible(suffix: str) -> bool:
    """True for the extensions a 3D view is offered for, installed or not."""

    return suffix.casefold() in MESH_EXTENSIONS


def unavailable_reason(suffix: str) -> str:
    """Why this install cannot build a mesh for the extension, or ""."""

    normalized = suffix.casefold()
    if normalized not in MESH_EXTENSIONS:
        return "not a mesh format"
    if normalized in geometry_preview.available_extensions():
        return ""
    extra = "preview" if normalized in geometry_preview.MESH_EXTENSIONS else "step"
    return f"needs the '{extra}' extra"


def mesh_store(workspace: Path | str) -> Path:
    """The gitignored directory holding cached mesh binaries."""

    return Path(workspace) / geometry_preview.CACHE_ROOT / CACHE_DIRNAME


def cache_key(path: Path, mtime_ns: int, st_size: int) -> str:
    """Normcased path, modification time, size, and the format version."""

    raw = "\0".join(
        [os.path.normcase(str(path)), str(mtime_ns), str(st_size), f"mesh{MESH_FORMAT_VERSION}"]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_path(store: Path | str, key: str) -> Path:
    """Sharded by the first two hex characters, as previews are."""

    return Path(store) / key[:2] / f"{key}.mesh"


def read_header(data: bytes) -> tuple[int, int, tuple[float, ...]]:
    """(format version, triangle count, bounding box) from a mesh binary."""

    magic, version, count, *box = HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        raise ValueError("not a PIHTI mesh")
    return version, count, tuple(box)


def encode(triangles) -> bytes:
    """The binary for an (N, 3, 3) triangle array, degenerate faces dropped."""

    import numpy as np

    from pihti_dedup import mesh_render

    tris = mesh_render._clean(np.asarray(triangles, dtype=np.float32))
    count = int(tris.shape[0])
    if count == 0:
        raise mesh_render.EmptyMeshError("no renderable triangles")
    wide = tris.astype(np.float64)
    normals = np.cross(wide[:, 1] - wide[:, 0], wide[:, 2] - wide[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-30)
    flat = np.repeat(normals[:, None, :], 3, axis=1).astype("<f4")
    points = tris.reshape(-1, 3)
    low, high = points.min(axis=0), points.max(axis=0)
    header = HEADER.pack(MAGIC, MESH_FORMAT_VERSION, count, *low.tolist(), *high.tolist())
    return header + tris.astype("<f4").tobytes() + flat.tobytes()


def build(path: Path | str) -> MeshResult:
    """Load and encode one file. Never raises."""

    target = Path(path)
    reason = unavailable_reason(target.suffix)
    if reason:
        return MeshResult(reason=reason)
    try:
        triangles = geometry_preview.load_triangles(target)
        if triangles is None:
            return MeshResult(reason=unavailable_reason(target.suffix) or "not a mesh format")
        if len(triangles) > MAX_TRIANGLES:
            return MeshResult(reason=TOO_LARGE, triangles=len(triangles))
        data = encode(triangles)
    except FileNotFoundError:
        return MeshResult(reason="no such workspace file")
    except Exception:  # any parse failure keeps the still image
        log.warning("mesh build failed for %s", target, exc_info=True)
        return MeshResult(reason=UNREADABLE)
    _version, count, _box = read_header(data)
    return MeshResult(data=data, triangles=count)


def read_cached(store: Path | str, key: str) -> bytes | None:
    try:
        return cache_path(store, key).read_bytes()
    except OSError:
        return None


def write_cached(store: Path | str, key: str, data: bytes) -> bool:
    """Store a mesh, temp-then-replace. False when the write failed."""

    destination = cache_path(store, key)
    temporary = destination.with_name(f"{destination.name}.{os.getpid():x}.{id(data):x}.tmp")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(data)
        temporary.replace(destination)
    except OSError:
        log.warning("could not cache a mesh at %s", destination, exc_info=True)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def get_or_build(
    workspace: Path | str, path: Path | str, mtime_ns: int, st_size: int
) -> MeshResult:
    """Disk-cached `build`. The cap is read at call time, so it can be lowered."""

    target = Path(path)
    reason = unavailable_reason(target.suffix)
    if reason:
        return MeshResult(reason=reason)
    store = mesh_store(workspace)
    key = cache_key(target, mtime_ns, st_size)
    cached = read_cached(store, key)
    if cached is not None:
        try:
            _version, count, _box = read_header(cached)
        except (ValueError, struct.error):
            cached = None
        else:
            if count > MAX_TRIANGLES:
                return MeshResult(reason=TOO_LARGE, triangles=count)
            return MeshResult(data=cached, triangles=count)
    result = build(target)
    if result.data is not None:
        write_cached(store, key, result.data)
    return result


def warm_meshes(workspace: Path | str, *, include_vendor: bool = False, progress=None):
    """Build every missing mesh for a workspace, once. Returns a `WarmResult`.

    A file over the cap is reported as "too large", not as a failure: its
    still preview is the intended view.
    """

    from pihti_dedup.inventory import scan_workspace

    root = Path(workspace).resolve()
    store = mesh_store(root)
    buildable = MESH_EXTENSIONS & geometry_preview.available_extensions()
    inventory = scan_workspace(root, include_vendor=include_vendor, hash_files=False)
    targets = [
        record for record in inventory.records if Path(record.path).suffix.casefold() in buildable
    ]
    built = cached = failed = 0
    failures: list[str] = []
    started = time.perf_counter()
    for index, record in enumerate(targets, start=1):
        target = root / record.path
        began = time.perf_counter()
        try:
            stat = target.stat()
        except OSError as exc:
            failed += 1
            failures.append(f"{record.path}: {exc}")
            continue
        key = cache_key(target, stat.st_mtime_ns, stat.st_size)
        if cache_path(store, key).is_file():
            cached += 1
            state = "cached"
        else:
            result = build(target)
            if result.data is not None:
                write_cached(store, key, result.data)
                built += 1
                state = "built"
            elif result.reason == TOO_LARGE:
                state = "too large"
            else:
                failed += 1
                failures.append(f"{record.path}: {result.reason}")
                state = "failed"
        if progress is not None:
            progress(index, len(targets), record.path, state, time.perf_counter() - began)
    return geometry_preview.WarmResult(
        considered=len(targets),
        rendered=built,
        cached=cached,
        failed=failed,
        seconds=time.perf_counter() - started,
        failures=tuple(failures),
    )
