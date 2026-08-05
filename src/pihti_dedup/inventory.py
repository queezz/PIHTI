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
from pathlib import Path
from typing import Iterable, Sequence

CAD_EXTENSIONS = frozenset(
    {".3mf", ".dwg", ".dxf", ".iam", ".idw", ".ipj", ".ipn", ".ipt", ".step", ".stl", ".stp"}
)
DEFAULT_SKIP_DIRS = frozenset(
    {".git", ".pytest_cache", ".ruff_cache", "__pycache__", "_site", "staging"}
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

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["records"] = [asdict(record) for record in self.records]
        return payload


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
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _system_for(path: str) -> str:
    parts = Path(path).parts
    return parts[0] if len(parts) > 1 else "."


def _vendor_reason(path: Path, display_root: Path) -> str | None:
    try:
        parts = tuple(part.casefold() for part in path.resolve().relative_to(display_root).parts)
    except ValueError:
        return None
    if len(parts) >= 2 and parts[:2] in VENDOR_PREFIXES:
        return "Pack-and-Go vendor support"
    return None


def _directory_exclusion(
    path: Path,
    display_root: Path,
    skip_dirs: set[str],
    *,
    include_oldversions: bool,
    include_vendor: bool,
) -> str | None:
    if path.name.casefold() in skip_dirs:
        return "excluded directory"
    if not include_oldversions and path.name.casefold() == "oldversions":
        return "Inventor save history"
    if not include_vendor:
        return _vendor_reason(path, display_root)
    return None


def _iter_files(
    roots: Sequence[Path],
    display_root: Path,
    extensions: set[str] | None,
    skip_dirs: set[str],
    *,
    include_oldversions: bool,
    include_vendor: bool,
) -> tuple[list[Path], list[ExcludedPath], list[str]]:
    files: list[Path] = []
    excluded: list[ExcludedPath] = []
    errors: list[str] = []

    for root in roots:
        if root.is_file():
            if extensions is None or root.suffix.casefold() in extensions:
                files.append(root)
            continue
        if not root.exists():
            errors.append(f"missing path: {root}")
            continue
        def record_walk_error(error: OSError) -> None:
            errors.append(f"cannot traverse {relative_path(Path(error.filename or root), display_root)}: {error}")

        for dirpath, dirnames, filenames in os.walk(root, onerror=record_walk_error):
            folder = Path(dirpath)
            kept_dirs: list[str] = []
            for dirname in dirnames:
                candidate = folder / dirname
                reason = _directory_exclusion(
                    candidate,
                    display_root,
                    skip_dirs,
                    include_oldversions=include_oldversions,
                    include_vendor=include_vendor,
                )
                if reason:
                    excluded.append(ExcludedPath(relative_path(candidate, display_root), reason))
                else:
                    kept_dirs.append(dirname)
            dirnames[:] = kept_dirs
            for filename in filenames:
                path = folder / filename
                if extensions is None or path.suffix.casefold() in extensions:
                    files.append(path)

    unique_files: dict[str, Path] = {}
    for path in files:
        unique_files.setdefault(os.path.normcase(str(path.resolve())), path)
    files = sorted(
        unique_files.values(), key=lambda path: relative_path(path, display_root).casefold()
    )
    excluded.sort(key=lambda item: item.path.casefold())
    return files, excluded, errors


def _make_group(kind: str, records: Sequence[FileRecord], title: str) -> DuplicateGroup:
    ordered = tuple(sorted(records, key=lambda record: record.path.casefold()))
    names = tuple(sorted({record.name for record in ordered}, key=str.casefold))
    hashes = tuple(sorted({record.sha256 for record in ordered if record.sha256}))
    systems = tuple(sorted({record.system for record in ordered}, key=str.casefold))
    extensions = tuple(sorted({record.suffix for record in ordered}))
    signature = "\n".join(
        [kind, *[f"{record.path}\0{record.sha256 or ''}" for record in ordered]]
    )
    group_id = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]

    hash_buckets: dict[str, list[FileRecord]] = defaultdict(list)
    for record in ordered:
        if record.sha256:
            hash_buckets[record.sha256].append(record)
    redundant_bytes = sum(
        group[0].size * (len(group) - 1) for group in hash_buckets.values() if len(group) > 1
    )
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
    )


def classify(records: Sequence[FileRecord]) -> tuple[tuple[DuplicateGroup, ...], tuple[DuplicateGroup, ...]]:
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
        filename_groups.append(_make_group(kind, group, sorted(group, key=lambda r: r.name)[0].name))

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
    roots = [Path(path) for path in paths]
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
    for path in files:
        try:
            stat = path.stat()
            digest = sha256_file(path) if hash_files else None
        except OSError as exc:
            errors.append(f"cannot read {relative_path(path, root)}: {exc}")
            continue
        relative = relative_path(path, root)
        records.append(
            FileRecord(
                path=relative,
                name=path.name,
                name_key=path.name.casefold(),
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
        extensions=(tuple(sorted(normalized_extensions)) if normalized_extensions is not None else None),
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
