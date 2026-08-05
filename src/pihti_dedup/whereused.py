"""Which assemblies and drawings name a given CAD file.

`PIHTI.ipj` sets `UsingUniqueFilenames=Yes` with the workspace at `.`, so
Inventor resolves a broken reference by *filename* rather than by stored path.
That makes the useful question "which documents name `bearing.ipt`?", not
"which documents point at `BoronProbe/parts/bearing.ipt`?", and it is why this
index is keyed on the casefolded filename.

The reference itself is read out of the referring document's raw bytes. An
`.iam`, `.idw`, or `.ipn` stores the path of every document it consumes as a
UTF-16LE string, so scanning for the UTF-16LE form of a CAD extension and
walking backwards to the nearest path separator recovers the filename without
Inventor, COM, or an OLE parse. The same technique identified the authored home
of the BoronProbe bearing parts on 2026-08-05.

Nothing here writes to a CAD file.
"""

from __future__ import annotations

import os
import re
import threading
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

#: Documents that can refer to another document.
REFERRING_EXTENSIONS = frozenset({".iam", ".idw", ".ipn"})
#: Documents that can be referred to.
REFERENCED_EXTENSIONS = frozenset({".iam", ".idw", ".ipn", ".ipt"})

#: Never walked: tool state and build output, not workspace content.
BASE_SKIP_DIRS = frozenset(
    {".git", ".pihti-dedup", ".pytest_cache", ".ruff_cache", "__pycache__", "_site"}
)
#: Inventor's filename search reaches everything under the workspace, including
#: `OldVersions/` and Pack-and-Go vendor trees, so a collision check must too.
RESOLUTION_SKIP_DIRS = BASE_SKIP_DIRS
#: A referrer, by contrast, is a document the owner would actually open, so save
#: history is excluded from the where-used answer.
REFERRER_SKIP_DIRS = BASE_SKIP_DIRS | {"oldversions"}

# The UTF-16LE form of a CAD extension. The interleaved NUL bytes carry no case,
# so IGNORECASE on the letter bytes alone matches `.IPT` as well as `.ipt`.
_EXTENSION_RE = re.compile(
    rb"\.\x00(?:i\x00p\x00t\x00|i\x00a\x00m\x00|i\x00d\x00w\x00|i\x00p\x00n\x00)",
    re.IGNORECASE,
)
# Walking backwards stops at a path separator or anything Windows forbids in a
# filename, which is what turns a stored path into the bare filename.
_NAME_STOP_CHARS = frozenset('\\/:*?"<>|')
_MAX_NAME_LENGTH = 240
_REPLACEMENT = "�"


def _is_name_char(char: str) -> bool:
    if len(char) != 1 or char == _REPLACEMENT:
        return False
    return char not in _NAME_STOP_CHARS and ord(char) >= 0x20


def extract_filenames(data: bytes) -> frozenset[str]:
    """Return every CAD filename embedded in `data` as a UTF-16LE string.

    Only the filename is returned: the stored path is deliberately discarded,
    because unique-filename resolution ignores it.
    """

    found: set[str] = set()
    for match in _EXTENSION_RE.finditer(data):
        start, end = match.start(), match.end()
        cursor = start
        while cursor - 2 >= 0 and start - cursor < _MAX_NAME_LENGTH * 2:
            if not _is_name_char(data[cursor - 2 : cursor].decode("utf-16-le", "replace")):
                break
            cursor -= 2
        if cursor == start:
            continue  # a bare extension with no stem is not a reference
        name = data[cursor:end].decode("utf-16-le", "replace")
        if _REPLACEMENT not in name:
            found.add(name)
    return frozenset(found)


def walk_workspace(
    root: Path,
    extensions: Iterable[str] | None = None,
    *,
    skip_dirs: Iterable[str] = RESOLUTION_SKIP_DIRS,
) -> Iterator[Path]:
    """Yield files under `root`, skipping directories by casefolded name.

    This is the plain directory walk Inventor's own filename search approximates;
    both the where-used index and the rename collision check are built on it.
    """

    wanted = {suffix.casefold() for suffix in extensions} if extensions else None
    skipped = {name.casefold() for name in skip_dirs}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name.casefold() not in skipped]
        folder = Path(dirpath)
        for filename in filenames:
            if wanted is None or Path(filename).suffix.casefold() in wanted:
                yield folder / filename


class ReferenceCache:
    """Embedded reference lists keyed by path and modification time.

    Reading the workspace's referring documents costs a couple of seconds of
    disk; the scan itself is cheap. Keying on `mtime_ns` means a resaved
    assembly is re-read and an untouched one is not.
    """

    def __init__(self, limit: int = 2048) -> None:
        self.limit = limit
        self._lock = threading.Lock()
        self._entries: OrderedDict[tuple[str, int], frozenset[str]] = OrderedDict()

    def names_for(self, path: Path, mtime_ns: int) -> frozenset[str]:
        key = (os.path.normcase(str(path)), mtime_ns)
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key]
        names = extract_filenames(path.read_bytes())
        with self._lock:
            self._entries[key] = names
            self._entries.move_to_end(key)
            while len(self._entries) > self.limit:
                self._entries.popitem(last=False)
        return names


@dataclass(frozen=True)
class WhereUsed:
    """Filename → referring documents, both workspace-relative."""

    root: Path
    referrers: dict[str, tuple[str, ...]]
    documents: int
    errors: tuple[str, ...] = ()

    def referring(self, filename: str) -> tuple[str, ...]:
        """Documents that name `filename`, excluding the file itself."""

        return self.referrers.get(filename.casefold(), ())

    def to_dict(self) -> dict:
        return {
            "documents": self.documents,
            "names": len(self.referrers),
            "errors": list(self.errors),
        }


def build_index(root: Path, *, cache: ReferenceCache | None = None) -> WhereUsed:
    """Scan every referring document under `root` and invert the references."""

    root = Path(root).resolve()
    cache = cache if cache is not None else ReferenceCache()
    referrers: dict[str, set[str]] = defaultdict(set)
    errors: list[str] = []
    documents = 0
    for path in walk_workspace(root, REFERRING_EXTENSIONS, skip_dirs=REFERRER_SKIP_DIRS):
        try:
            names = cache.names_for(path, path.stat().st_mtime_ns)
        except OSError as exc:
            errors.append(f"cannot read {path.name}: {exc}")
            continue
        documents += 1
        relative = path.relative_to(root).as_posix()
        for name in names:
            key = name.casefold()
            if key == path.name.casefold():
                continue  # a document naming itself is not a referrer
            referrers[key].add(relative)
    return WhereUsed(
        root=root,
        referrers={
            key: tuple(sorted(paths, key=str.casefold)) for key, paths in sorted(referrers.items())
        },
        documents=documents,
        errors=tuple(errors),
    )


def filename_locations(root: Path) -> dict[str, tuple[str, ...]]:
    """Casefolded CAD filename → every workspace path carrying that name.

    Save history and vendor trees are included on purpose: the repository
    invariant treats a repeated CAD filename *anywhere* in the workspace as an
    Inventor-resolution concern.
    """

    root = Path(root).resolve()
    locations: dict[str, list[str]] = defaultdict(list)
    for path in walk_workspace(root, REFERENCED_EXTENSIONS, skip_dirs=RESOLUTION_SKIP_DIRS):
        locations[path.name.casefold()].append(path.relative_to(root).as_posix())
    return {key: tuple(sorted(paths, key=str.casefold)) for key, paths in locations.items()}
