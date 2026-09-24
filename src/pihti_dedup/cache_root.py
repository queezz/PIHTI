"""Where the machine-local caches live: outside the workspace and outside Dropbox.

A preview PNG and a mesh binary are rebuilt from the CAD file whenever they
are missing, and a whole workspace of them is hundreds of megabytes that
change on every resave. Kept beside the workspace they would sync through
Dropbox to every machine, so they live under one machine-local root instead:

    <base>/<workspace-id>/previews/
    <base>/<workspace-id>/meshes/

`<base>` is the `PIHTI_DEDUP_CACHE_ROOT` environment variable when it is set,
otherwise `%LOCALAPPDATA%\\pihti-dedup` on Windows and `~/.cache/pihti-dedup`
elsewhere. `<workspace-id>` is the workspace folder's name plus the first 12
hex characters of the SHA-256 of its resolved path, so two checkouts never
share a cache and the owner can still tell which folder is which.

A Windows AppData path is trusted by its resolved location, never by its
spelling: a packaged desktop app can give its process tree a private view of
`%LOCALAPPDATA%` under `AppData\\Local\\Packages\\<package>\\LocalCache`. A
base that resolves there is refused with an error naming it, rather than
filling a cache nobody else can see.

The inventory snapshots and the quarantine store stay in the workspace's
`.pihti-dedup/`; they are small, or data the owner may want beside it.
"""

from __future__ import annotations

import hashlib
import os
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

#: Overrides the base directory; the workspace id is still appended.
ENV_VAR = "PIHTI_DEDUP_CACHE_ROOT"
APP_DIRNAME = "pihti-dedup"
ID_HEX = 12


class CacheRootError(RuntimeError):
    """The cache root resolves somewhere this tool refuses to write."""


def default_base(
    platform: str | None = None, environ: Mapping[str, str] | None = None
) -> Path:
    """The base directory before resolution: the override, else the OS default."""

    env = os.environ if environ is None else environ
    override = env.get(ENV_VAR, "").strip()
    if override:
        return Path(override).expanduser()
    if (platform or sys.platform).startswith("win"):
        local = env.get("LOCALAPPDATA", "").strip()
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / APP_DIRNAME
    return Path.home() / ".cache" / APP_DIRNAME


def is_virtualized(path: Path | str) -> bool:
    """True for a path inside a packaged app's private AppData tree."""

    folded = str(path).replace("/", "\\").casefold()
    return "\\appdata\\local\\packages\\" in folded and "\\localcache" in folded


def workspace_id(workspace: Path | str) -> str:
    """The folder name plus 12 hex characters of its resolved path's SHA-256."""

    resolved = Path(workspace).resolve()
    digest = hashlib.sha256(str(resolved).encode("utf-8", "surrogatepass")).hexdigest()
    return f"{resolved.name or 'workspace'}-{digest[:ID_HEX]}"


@lru_cache(maxsize=32)
def _root(base: str, workspace: str) -> Path:
    resolved = Path(base).resolve()
    if is_virtualized(resolved):
        raise CacheRootError(
            f"refusing the cache root {resolved}: it is inside a packaged app's private "
            f"AppData tree (Packages\\...\\LocalCache), which other programs cannot see. "
            f"Run from an ordinary terminal or set {ENV_VAR} to a folder outside it."
        )
    return resolved / workspace_id(workspace)


def cache_root(workspace: Path | str) -> Path:
    """`<base>/<workspace-id>/` for this workspace. Creates nothing.

    Raises `CacheRootError` when the base resolves into a virtualized packaged
    app tree.
    """

    return _root(str(default_base()), str(workspace))
