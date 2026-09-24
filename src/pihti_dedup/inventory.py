"""Filesystem inventory and duplicate classification.

The Inventor project uses unique filenames, so repeated filename groups are the
primary review surface. SHA-256 is deliberately a secondary classification: it
proves byte identity, not geometry or reference safety.
"""

from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import Iterable, Sequence

CAD_EXTENSIONS = frozenset(
    {".3mf", ".dwg", ".dxf", ".iam", ".idw", ".ipj", ".ipn", ".ipt", ".step", ".stl", ".stp"}
)
DEFAULT_SKIP_DIRS = frozenset(
    {".git", ".pihti-dedup", ".pytest_cache", ".ruff_cache", "__pycache__", "_site", "staging"}
)
VENDOR_PREFIXES = frozenset({("bellows", "design data"), ("bellows", "templates")})
HASH_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class FileRecord:
    path: str
    name: str
    name_key: str
    suffix: str
    size: int
    mtime_ns: int
    sha256: str | None
    system: str


@dataclass(frozen=True)
class ExcludedPath:
    path: str
    reason: str


@dataclass(frozen=True)
class DuplicateGroup:
    id: str
    kind: str
    title: str
    names: tuple[str, ...]
    records: tuple[FileRecord, ...]
    hashes: tuple[str, ...]
    systems: tuple[str, ...]
    extensions: tuple[str, ...]
    cross_folder: bool
    redundant_bytes: int
    characterization: str | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["records"] = [asdict(record) for record in self.records]
        return payload


#: Autodesk support article "While working with Inventor newVer files are
#: created": during a save Inventor writes the new state to
#: `<name>.newVer.<ext>` and removes it when the save completes. A leftover
#: means that last step did not run, typically because another program (a
#: sync client such as Dropbox) held the file.
NEWVER_EXPLANATION = (
    "Inventor writes this file during a save and removes it when the save completes; "
    "it stays behind when another program, such as a sync client, held the file."
)


@dataclass(frozen=True)
class SaveLeftover:
    """A `.newVer` file that is not a plain identical leftover.

    `state` is `differs` (its base file exists with other bytes) or `orphan`
    (no base file beside it).
    """

    path: str
    base_path: str
    state: str
    record: FileRecord
    base: FileRecord | None = None


@dataclass(frozen=True)
class Inventory:
    root: Path
    records: tuple[FileRecord, ...]
    filename_groups: tuple[DuplicateGroup, ...]
    renamed_groups: tuple[DuplicateGroup, ...]
    excluded: tuple[ExcludedPath, ...]
    errors: tuple[str, ...]
    include_vendor: bool
    extensions: tuple[str, ...] | None
    generated_at: str

    @property
    def groups(self) -> tuple[DuplicateGroup, ...]:
        return self.filename_groups + self.renamed_groups

    @cached_property
    def split_groups(self) -> tuple[DuplicateGroup, ...]:
        """Identical-copy groups carved out of same-name, different-byte groups.

        Every hash bucket of two or more members inside a collision group is
        a byte-identical copy set of its own; members with a unique hash are
        a name clash only and belong to Doctor, not to Duplicates.
        """

        return split_exact_groups(self.filename_groups)

    @property
    def duplicate_groups(self) -> tuple[DuplicateGroup, ...]:
        """What the Duplicates view lists: byte-identical groups only."""

        identical = [group for group in self.filename_groups if group.kind == "exact"]
        identical.extend(self.split_groups)
        identical.sort(key=lambda group: (-len(group.records), group.title.casefold()))
        return tuple(identical) + self.renamed_groups

    @property
    def name_clash_groups(self) -> tuple[DuplicateGroup, ...]:
        """Same name, bytes differing or not compared: Doctor's business."""

        return tuple(
            group for group in self.filename_groups if group.kind in {"collision", "unverified"}
        )

    def find_group(self, group_id: str) -> DuplicateGroup | None:
        return next(
            (group for group in (*self.groups, *self.split_groups) if group.id == group_id),
            None,
        )

    @cached_property
    def save_leftovers(self) -> tuple[SaveLeftover, ...]:
        """`.newVer` files that differ from their base file or have none."""

        return interrupted_saves(self.records)

    @property
    def summary(self) -> dict[str, int]:
        exact = sum(group.kind == "exact" for group in self.filename_groups)
        collisions = sum(group.kind == "collision" for group in self.filename_groups)
        unverified = sum(group.kind == "unverified" for group in self.filename_groups)
        files_in_filename_groups = sum(len(group.records) for group in self.filename_groups)

        by_hash: dict[str, list[FileRecord]] = defaultdict(list)
        for record in self.records:
            if record.sha256:
                by_hash[record.sha256].append(record)
        redundant_bytes = sum(
            group[0].size * (len(group) - 1) for group in by_hash.values() if len(group) > 1
        )

        return {
            "files": len(self.records),
            "bytes": sum(record.size for record in self.records),
            "filename_groups": len(self.filename_groups),
            "files_in_filename_groups": files_in_filename_groups,
            "exact_groups": exact,
            "collision_groups": collisions,
            "unverified_groups": unverified,
            "renamed_groups": len(self.renamed_groups),
            "redundant_bytes": redundant_bytes,
            "excluded_paths": len(self.excluded),
            "errors": len(self.errors),
        }

    def to_dict(self, *, include_files: bool = True) -> dict:
        payload = {
            "schema_version": 1,
            "root": ".",
            "workspace": self.root.name,
            "generated_at": self.generated_at,
            "scope": {
                "extensions": list(self.extensions) if self.extensions is not None else None,
                "include_vendor": self.include_vendor,
            },
            "summary": self.summary,
            "groups": [group.to_dict() for group in self.groups],
            "excluded": [asdict(item) for item in self.excluded],
            "errors": list(self.errors),
        }
        if include_files:
            payload["files"] = [asdict(record) for record in self.records]
        return payload


def normalize_extensions(values: Iterable[str] | None) -> set[str] | None:
    if not values:
        return None
    result = set()
    for value in values:
        suffix = value.casefold()
        result.add(suffix if suffix.startswith(".") else f".{suffix}")
    return result


def common_root(paths: Sequence[Path]) -> Path:
    resolved = [path.resolve() for path in paths]
    if len(resolved) == 1:
        return resolved[0] if resolved[0].is_dir() else resolved[0].parent
    return Path(os.path.commonpath([str(path) for path in resolved]))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_path(path: Path, root: Path) -> str:
    # Scanner paths are already absolute descendants of the resolved display
    # root.  Keep that common path lexical: resolving every one of the 1,200+
    # CAD files again turns a cheap metadata walk into most of a second on a
    # Dropbox-backed Windows workspace.
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return path.resolve().as_posix()


def _system_for(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else "."


def _directory_exclusion(
    name: str,
    relative_path: str,
    skip_dirs: set[str],
    *,
    include_oldversions: bool,
    include_vendor: bool,
) -> str | None:
    """Reason to skip directory `name`, whose display-relative path is `relative_path`."""

    folded = name.casefold()
    if folded in skip_dirs:
        return "excluded directory"
    if not include_oldversions and folded == "oldversions":
        return "Inventor save history"
    if not include_vendor:
        parts = tuple(part.casefold() for part in relative_path.split("/"))
        if len(parts) >= 2 and parts[:2] in VENDOR_PREFIXES:
            return "Pack-and-Go vendor support"
    return None


def _relative_prefix(path: str, display_root: str) -> str | None:
    """Lexical display-relative POSIX path of `path`, or None when not beneath the root."""

    if os.path.normcase(path) == os.path.normcase(display_root):
        return ""
    prefix = display_root.rstrip("\\/") + os.sep
    if os.path.normcase(path).startswith(os.path.normcase(prefix)):
        return path[len(prefix) :].replace("\\", "/")
    return None


def _iter_files(
    roots: Sequence[Path],
    display_root: Path,
    extensions: set[str] | None,
    skip_dirs: set[str],
    *,
    include_oldversions: bool,
    include_vendor: bool,
) -> tuple[list[tuple[Path, str]], list[ExcludedPath], list[str]]:
    """Walk `roots` with `os.scandir` and return (path, display-relative path) pairs.

    The walk is string-based on purpose. Building a `Path` per entry and
    calling `relative_to` on each of the workspace's 1,200+ files made the
    metadata walk several times slower than the directory reads themselves.
    """

    files: list[tuple[Path, str]] = []
    excluded: list[ExcludedPath] = []
    errors: list[str] = []
    root_text = str(display_root)

    def relative_of(path: str) -> str:
        relative = _relative_prefix(path, root_text)
        return relative if relative is not None else relative_path(Path(path), display_root)

    def wanted(name: str) -> bool:
        return extensions is None or os.path.splitext(name)[1].casefold() in extensions

    for root in roots:
        if root.is_file():
            if extensions is None or root.suffix.casefold() in extensions:
                files.append((root, relative_of(str(root))))
            continue
        if not root.exists():
            errors.append(f"missing path: {root}")
            continue

        stack: list[tuple[str, str]] = [(str(root), relative_of(str(root)))]
        while stack:
            directory, relative_dir = stack.pop()
            try:
                with os.scandir(directory) as entries:
                    listing = list(entries)
            except OSError as error:
                errors.append(f"cannot traverse {relative_of(directory)}: {error}")
                continue
            subdirs: list[tuple[str, str]] = []
            for entry in listing:
                name = entry.name
                child_relative = f"{relative_dir}/{name}" if relative_dir else name
                try:
                    is_dir = entry.is_dir()
                except OSError:
                    is_dir = False
                if is_dir:
                    reason = _directory_exclusion(
                        name,
                        child_relative,
                        skip_dirs,
                        include_oldversions=include_oldversions,
                        include_vendor=include_vendor,
                    )
                    if reason:
                        excluded.append(ExcludedPath(child_relative, reason))
                    elif not entry.is_symlink():
                        subdirs.append((entry.path, child_relative))
                    continue
                if wanted(name):
                    files.append((Path(entry.path), child_relative))
            # Pop order does not matter: the result is sorted below.
            stack.extend(subdirs)

    unique_files: dict[str, tuple[Path, str]] = {}
    for path, relative in files:
        unique_files.setdefault(os.path.normcase(str(path)), (path, relative))
    ordered = sorted(unique_files.values(), key=lambda item: item[1].casefold())
    excluded.sort(key=lambda item: item.path.casefold())
    return ordered, excluded, errors


def _make_group(
    kind: str,
    records: Sequence[FileRecord],
    title: str,
    characterization: str | None = None,
) -> DuplicateGroup:
    ordered = tuple(sorted(records, key=lambda record: record.path.casefold()))
    names = tuple(sorted({record.name for record in ordered}, key=str.casefold))
    hashes = tuple(sorted({record.sha256 for record in ordered if record.sha256}))
    systems = tuple(sorted({record.system for record in ordered}, key=str.casefold))
    extensions = tuple(sorted({record.suffix for record in ordered}))
    signature = "\n".join([kind, *[f"{record.path}\0{record.sha256 or ''}" for record in ordered]])
    group_id = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]

    hash_buckets: dict[str, list[FileRecord]] = defaultdict(list)
    for record in ordered:
        if record.sha256:
            hash_buckets[record.sha256].append(record)
    redundant_bytes = sum(
        group[0].size * (len(group) - 1) for group in hash_buckets.values() if len(group) > 1
    )
    if kind == "renamed" and characterization is None:
        leftovers = newver_leftovers(ordered)
        if leftovers:
            characterization = "newver"
            title = f"Inventor save leftover — identical to {leftovers[0][1].name}"
    return DuplicateGroup(
        id=group_id,
        kind=kind,
        title=title,
        names=names,
        records=ordered,
        hashes=hashes,
        systems=systems,
        extensions=extensions,
        cross_folder=len(systems) > 1,
        redundant_bytes=redundant_bytes,
        characterization=characterization,
    )


NEWVER_MARKER = ".newver"


def newver_base_path(path: str) -> str | None:
    """The base file a `<name>.newVer.<ext>` save leftover belongs beside.

    Inventor writes the leftover in the base file's own folder, so the base
    path is the same folder with the `.newVer` marker removed.
    """

    folder, _, name = path.rpartition("/")
    stem, dot, suffix = name.rpartition(".")
    if not dot or not stem.casefold().endswith(NEWVER_MARKER) or len(stem) == len(NEWVER_MARKER):
        return None
    base = f"{stem[: -len(NEWVER_MARKER)]}.{suffix}"
    return f"{folder}/{base}" if folder else base


def newver_leftovers(
    records: Sequence[FileRecord],
) -> tuple[tuple[FileRecord, FileRecord], ...]:
    """(leftover, base) pairs inside one byte-identical group.

    A pair counts only when the base sits in the same folder with the same
    bytes and the same modified time: the save wrote the new state, and the
    original already was that state.
    """

    by_path = {record.path.casefold(): record for record in records}
    pairs = []
    for record in records:
        base_path = newver_base_path(record.path)
        base = by_path.get(base_path.casefold()) if base_path else None
        if (
            base is not None
            and record.sha256
            and record.sha256 == base.sha256
            and record.mtime_ns == base.mtime_ns
        ):
            pairs.append((record, base))
    return tuple(pairs)


def interrupted_saves(records: Sequence[FileRecord]) -> tuple[SaveLeftover, ...]:
    """`.newVer` leftovers whose base differs, and leftovers without a base.

    An identical leftover is a Duplicates matter and is not listed here. A
    pair whose bytes are not both known is not judged at all.
    """

    by_path = {record.path.casefold(): record for record in records}
    found: list[SaveLeftover] = []
    for record in records:
        base_path = newver_base_path(record.path)
        if base_path is None:
            continue
        base = by_path.get(base_path.casefold())
        if base is None:
            found.append(SaveLeftover(record.path, base_path, "orphan", record))
            continue
        if not record.sha256 or not base.sha256 or record.sha256 == base.sha256:
            continue
        found.append(SaveLeftover(record.path, base.path, "differs", record, base))
    found.sort(key=lambda item: (item.state != "differs", item.path.casefold()))
    return tuple(found)


def split_exact_groups(
    filename_groups: Sequence[DuplicateGroup],
) -> tuple[DuplicateGroup, ...]:
    """One `exact` group per shared hash inside each same-name collision group."""

    split: list[DuplicateGroup] = []
    for group in filename_groups:
        if group.kind != "collision":
            continue
        buckets: dict[str, list[FileRecord]] = defaultdict(list)
        for record in group.records:
            if record.sha256:
                buckets[record.sha256].append(record)
        for bucket in buckets.values():
            if len(bucket) > 1:
                split.append(_make_group("exact", bucket, group.title, characterization="split"))
    return tuple(split)


def classify(
    records: Sequence[FileRecord],
) -> tuple[tuple[DuplicateGroup, ...], tuple[DuplicateGroup, ...]]:
    by_name: dict[str, list[FileRecord]] = defaultdict(list)
    by_hash: dict[str, list[FileRecord]] = defaultdict(list)
    for record in records:
        by_name[record.name_key].append(record)
        if record.sha256:
            by_hash[record.sha256].append(record)

    filename_groups: list[DuplicateGroup] = []
    for group in by_name.values():
        if len(group) < 2:
            continue
        hashes = {record.sha256 for record in group if record.sha256}
        if len(hashes) > 1:
            kind = "collision"
        elif len(hashes) == 1 and all(record.sha256 for record in group):
            kind = "exact"
        else:
            kind = "unverified"
        filename_groups.append(
            _make_group(kind, group, sorted(group, key=lambda r: r.name)[0].name)
        )

    renamed_groups: list[DuplicateGroup] = []
    for group in by_hash.values():
        if len(group) > 1 and len({record.name_key for record in group}) > 1:
            renamed_groups.append(_make_group("renamed", group, "Identical bytes, different names"))

    priority = {"collision": 0, "unverified": 1, "exact": 2}
    filename_groups.sort(
        key=lambda group: (
            priority[group.kind],
            -len(group.records),
            group.title.casefold(),
        )
    )
    renamed_groups.sort(key=lambda group: (-len(group.records), group.names[0].casefold()))
    return tuple(filename_groups), tuple(renamed_groups)


def scan_paths(
    paths: Sequence[Path],
    *,
    display_root: Path | None = None,
    extensions: Iterable[str] | None = CAD_EXTENSIONS,
    skip_dirs: Iterable[str] = (),
    include_oldversions: bool = False,
    include_vendor: bool = False,
    include_staging: bool = False,
    hash_files: bool = True,
) -> Inventory:
    roots = [Path(path).resolve() for path in paths]
    root = display_root.resolve() if display_root else common_root(roots)
    normalized_extensions = normalize_extensions(extensions)
    normalized_skips = {name.casefold() for name in DEFAULT_SKIP_DIRS | set(skip_dirs)}
    if include_staging:
        normalized_skips.discard("staging")
    files, excluded, errors = _iter_files(
        roots,
        root,
        normalized_extensions,
        normalized_skips,
        include_oldversions=include_oldversions,
        include_vendor=include_vendor,
    )

    records: list[FileRecord] = []
    for path, relative in files:
        try:
            stat = path.stat()
            digest = sha256_file(path) if hash_files else None
        except OSError as exc:
            errors.append(f"cannot read {relative}: {exc}")
            continue
        name = relative.rsplit("/", 1)[-1]
        records.append(
            FileRecord(
                path=relative,
                name=name,
                name_key=name.casefold(),
                suffix=path.suffix.casefold(),
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                sha256=digest,
                system=_system_for(relative),
            )
        )

    records.sort(key=lambda record: record.path.casefold())
    filename_groups, renamed_groups = classify(records)
    return Inventory(
        root=root,
        records=tuple(records),
        filename_groups=filename_groups,
        renamed_groups=renamed_groups,
        excluded=tuple(excluded),
        errors=tuple(errors),
        include_vendor=include_vendor,
        extensions=(
            tuple(sorted(normalized_extensions)) if normalized_extensions is not None else None
        ),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def scan_workspace(
    root: Path,
    *,
    include_vendor: bool = False,
    hash_files: bool = True,
    extensions: Iterable[str] | None = CAD_EXTENSIONS,
) -> Inventory:
    return scan_paths(
        [root],
        display_root=root,
        extensions=extensions,
        include_vendor=include_vendor,
        hash_files=hash_files,
    )


def legacy_groups(records: Sequence[FileRecord]) -> dict[str, list[list[FileRecord]]]:
    by_hash: dict[str, list[FileRecord]] = defaultdict(list)
    by_name: dict[str, list[FileRecord]] = defaultdict(list)
    by_name_size: dict[tuple[str, int], list[FileRecord]] = defaultdict(list)
    for record in records:
        if record.sha256:
            by_hash[record.sha256].append(record)
        by_name[record.name_key].append(record)
        by_name_size[(record.name_key, record.size)].append(record)

    groups = {
        "hash_duplicates": [group for group in by_hash.values() if len(group) > 1],
        "renamed_hash_duplicates": [
            group
            for group in by_hash.values()
            if len(group) > 1 and len({record.name_key for record in group}) > 1
        ],
        "same_name_same_size": [group for group in by_name_size.values() if len(group) > 1],
        "same_name_different_size": [
            group
            for group in by_name.values()
            if len(group) > 1 and len({record.size for record in group}) > 1
        ],
    }
    for values in groups.values():
        for group in values:
            group.sort(key=lambda record: record.path.casefold())
        values.sort(key=lambda group: (-len(group), group[0].name_key, group[0].size))
    return groups
