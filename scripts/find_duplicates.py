#!/usr/bin/env python3
"""
find_duplicates.py
------------------
Inventory files and report duplicate/copy candidates in an engineering archive.

The tool is read-only. It never deletes, moves, or rewrites CAD files.

It reports:
  - hash duplicates: byte-for-byte identical files, even if renamed
  - renamed hash duplicates: exact duplicates whose filenames differ
  - same-name/same-size groups: likely direct copies before hash review
  - same-name/different-size groups: possible version forks

Usage:
    python scripts/find_duplicates.py . --markdown duplicate-report.md
    python scripts/find_duplicates.py staging/hayashi "Plasma Vessel" --json duplicates.json
    python scripts/find_duplicates.py . --extensions .ipt .iam .stp .step .stl
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_SKIP_DIRS = {".git", "_site", "__pycache__", ".pytest_cache", ".ruff_cache"}
DEFAULT_SKIP_PARTS = {"OldVersions"}
HASH_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class FileRecord:
    path: str
    name: str
    suffix: str
    size: int
    mtime_ns: int
    sha256: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory files and report duplicate/copy candidates."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to scan. Defaults to current directory.",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Root used for display-relative paths. Defaults to common parent.",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=None,
        help="Optional extension filter, e.g. .ipt .iam .stp .step .stl.",
    )
    parser.add_argument(
        "--skip-dir",
        action="append",
        default=[],
        help="Additional directory name to skip. Can be repeated.",
    )
    parser.add_argument(
        "--include-oldversions",
        action="store_true",
        help="Include folders named OldVersions. Skipped by default.",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Skip SHA-256 calculation; same-name/size inventory only.",
    )
    parser.add_argument("--json", default=None, help="Write full report as JSON.")
    parser.add_argument("--markdown", default=None, help="Write summary report as Markdown.")
    parser.add_argument("--csv", default=None, help="Write file inventory as CSV.")
    parser.add_argument(
        "--max-group-lines",
        type=int,
        default=200,
        help="Maximum detailed lines per Markdown section. Default: 200.",
    )
    return parser.parse_args()


def normalize_extensions(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    result = set()
    for value in values:
        ext = value.lower()
        if not ext.startswith("."):
            ext = "." + ext
        result.add(ext)
    return result


def common_root(paths: list[Path]) -> Path:
    existing = [p.resolve() for p in paths]
    if len(existing) == 1:
        p = existing[0]
        return p if p.is_dir() else p.parent
    return Path(os.path.commonpath([str(p) for p in existing]))


def should_skip_dir(path: Path, skip_dirs: set[str], include_oldversions: bool) -> bool:
    if path.name in skip_dirs:
        return True
    if not include_oldversions and any(part == "OldVersions" for part in path.parts):
        return True
    return False


def iter_files(
    roots: list[Path],
    extensions: set[str] | None,
    skip_dirs: set[str],
    include_oldversions: bool,
) -> Iterable[Path]:
    for root in roots:
        if root.is_file():
            if extensions is None or root.suffix.lower() in extensions:
                yield root
            continue
        if not root.exists():
            print(f"warning: missing path: {root}", file=sys.stderr)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirpath_p = Path(dirpath)
            dirnames[:] = [
                d
                for d in dirnames
                if not should_skip_dir(dirpath_p / d, skip_dirs, include_oldversions)
            ]
            for filename in filenames:
                path = dirpath_p / filename
                if extensions is None or path.suffix.lower() in extensions:
                    yield path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def inventory(args: argparse.Namespace) -> tuple[list[FileRecord], Path]:
    roots = [Path(p) for p in args.paths]
    display_root = Path(args.root).resolve() if args.root else common_root(roots)
    extensions = normalize_extensions(args.extensions)
    skip_dirs = set(DEFAULT_SKIP_DIRS) | set(args.skip_dir)
    records: list[FileRecord] = []
    for path in iter_files(roots, extensions, skip_dirs, args.include_oldversions):
        try:
            stat = path.stat()
            digest = None if args.no_hash else sha256_file(path)
        except OSError as exc:
            print(f"warning: cannot read {path}: {exc}", file=sys.stderr)
            continue
        records.append(
            FileRecord(
                path=rel(path, display_root),
                name=path.name,
                suffix=path.suffix.lower(),
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                sha256=digest,
            )
        )
    records.sort(key=lambda r: r.path.lower())
    return records, display_root


def group_records(records: list[FileRecord]) -> dict[str, list[list[FileRecord]]]:
    by_hash: dict[str, list[FileRecord]] = defaultdict(list)
    by_name: dict[str, list[FileRecord]] = defaultdict(list)
    by_name_size: dict[tuple[str, int], list[FileRecord]] = defaultdict(list)

    for record in records:
        if record.sha256:
            by_hash[record.sha256].append(record)
        by_name[record.name.lower()].append(record)
        by_name_size[(record.name.lower(), record.size)].append(record)

    hash_duplicates = [group for group in by_hash.values() if len(group) > 1]
    renamed_hash_duplicates = [
        group for group in hash_duplicates if len({r.name.lower() for r in group}) > 1
    ]
    same_name_same_size = [group for group in by_name_size.values() if len(group) > 1]
    same_name_different_size = [
        group for group in by_name.values() if len(group) > 1 and len({r.size for r in group}) > 1
    ]

    for groups in (
        hash_duplicates,
        renamed_hash_duplicates,
        same_name_same_size,
        same_name_different_size,
    ):
        groups.sort(key=lambda g: (-len(g), g[0].name.lower(), g[0].size))
        for group in groups:
            group.sort(key=lambda r: r.path.lower())

    return {
        "hash_duplicates": hash_duplicates,
        "renamed_hash_duplicates": renamed_hash_duplicates,
        "same_name_same_size": same_name_same_size,
        "same_name_different_size": same_name_different_size,
    }


def groups_to_json(groups: dict[str, list[list[FileRecord]]]) -> dict[str, list[list[dict]]]:
    return {name: [[asdict(record) for record in group] for group in values] for name, values in groups.items()}


def write_csv(path: Path, records: list[FileRecord]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(records[0]).keys()) if records else ["path", "name", "suffix", "size", "mtime_ns", "sha256"])
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def markdown_group(group: list[FileRecord]) -> list[str]:
    names = sorted({r.name for r in group})
    size = group[0].size
    digest = group[0].sha256 or "not hashed"
    lines = [f"- {len(group)} files, {size} bytes, names: `{', '.join(names)}`"]
    lines.append(f"  - sha256: `{digest}`")
    for record in group:
        lines.append(f"  - `{record.path}`")
    return lines


def write_markdown(
    path: Path,
    records: list[FileRecord],
    groups: dict[str, list[list[FileRecord]]],
    display_root: Path,
    max_group_lines: int,
) -> None:
    total_bytes = sum(r.size for r in records)
    lines = [
        "# Duplicate Inventory Report",
        "",
        f"Root: `{display_root}`",
        f"Files scanned: **{len(records)}**",
        f"Bytes scanned: **{total_bytes}**",
        "",
        "## Summary",
        "",
        "| Category | Groups | Files in groups |",
        "| --- | ---: | ---: |",
    ]
    for key, label in [
        ("hash_duplicates", "Hash duplicates"),
        ("renamed_hash_duplicates", "Renamed hash duplicates"),
        ("same_name_same_size", "Same name + same size"),
        ("same_name_different_size", "Same name + different size"),
    ]:
        grouped_files = sum(len(group) for group in groups[key])
        lines.append(f"| {label} | {len(groups[key])} | {grouped_files} |")

    for key, heading in [
        ("hash_duplicates", "Hash Duplicates"),
        ("renamed_hash_duplicates", "Renamed Hash Duplicates"),
        ("same_name_same_size", "Same Name + Same Size"),
        ("same_name_different_size", "Same Name + Different Size"),
    ]:
        lines.extend(["", f"## {heading}", ""])
        if not groups[key]:
            lines.append("None.")
            continue
        emitted = 0
        for group in groups[key]:
            group_lines = markdown_group(group)
            if emitted + len(group_lines) > max_group_lines:
                remaining = len(groups[key]) - groups[key].index(group)
                lines.append(f"- ... truncated {remaining} more groups. Use `--json` for the full report.")
                break
            lines.extend(group_lines)
            emitted += len(group_lines)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    records, display_root = inventory(args)
    groups = group_records(records)

    print(f"files scanned: {len(records)}")
    print(f"hash duplicate groups: {len(groups['hash_duplicates'])}")
    print(f"renamed hash duplicate groups: {len(groups['renamed_hash_duplicates'])}")
    print(f"same-name/same-size groups: {len(groups['same_name_same_size'])}")
    print(f"same-name/different-size groups: {len(groups['same_name_different_size'])}")

    if args.csv:
        write_csv(Path(args.csv), records)
    if args.json:
        payload = {
            "root": str(display_root),
            "files": [asdict(record) for record in records],
            "groups": groups_to_json(groups),
        }
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        write_markdown(Path(args.markdown), records, groups, display_root, args.max_group_lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())