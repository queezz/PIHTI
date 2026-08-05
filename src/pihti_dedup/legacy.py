"""Compatibility CLI for ``scripts/find_duplicates.py``."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Sequence

from pihti_dedup.inventory import FileRecord, legacy_groups, scan_paths


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inventory files and report duplicate candidates.")
    parser.add_argument("paths", nargs="*", default=["."])
    parser.add_argument("--root", default=None)
    parser.add_argument("--extensions", nargs="*", default=None)
    parser.add_argument("--skip-dir", action="append", default=[])
    parser.add_argument("--include-oldversions", action="store_true")
    parser.add_argument("--no-hash", action="store_true")
    parser.add_argument("--json", default=None)
    parser.add_argument("--markdown", default=None)
    parser.add_argument("--csv", default=None)
    parser.add_argument("--max-group-lines", type=int, default=200)
    return parser


def _groups_to_json(groups: dict[str, list[list[FileRecord]]]) -> dict:
    return {
        name: [[_legacy_record(record) for record in group] for group in values]
        for name, values in groups.items()
    }


def _legacy_record(record: FileRecord) -> dict:
    return {
        "path": record.path,
        "name": record.name,
        "suffix": record.suffix,
        "size": record.size,
        "mtime_ns": record.mtime_ns,
        "sha256": record.sha256,
    }


def _write_csv(path: Path, records: Sequence[FileRecord]) -> None:
    fields = ["path", "name", "suffix", "size", "mtime_ns", "sha256"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(_legacy_record(record))


def _markdown_group(group: list[FileRecord]) -> list[str]:
    names = sorted({record.name for record in group})
    digest = group[0].sha256 or "not hashed"
    lines = [f"- {len(group)} files, {group[0].size} bytes, names: `{', '.join(names)}`"]
    lines.append(f"  - sha256: `{digest}`")
    lines.extend(f"  - `{record.path}`" for record in group)
    return lines


def _write_markdown(
    path: Path,
    records: Sequence[FileRecord],
    groups: dict[str, list[list[FileRecord]]],
    display_root: Path,
    max_group_lines: int,
) -> None:
    labels = [
        ("hash_duplicates", "Hash Duplicates"),
        ("renamed_hash_duplicates", "Renamed Hash Duplicates"),
        ("same_name_same_size", "Same Name + Same Size"),
        ("same_name_different_size", "Same Name + Different Size"),
    ]
    lines = [
        "# Duplicate Inventory Report",
        "",
        f"Root: `{display_root}`",
        f"Files scanned: **{len(records)}**",
        f"Bytes scanned: **{sum(record.size for record in records)}**",
        "",
        "## Summary",
        "",
        "| Category | Groups | Files in groups |",
        "| --- | ---: | ---: |",
    ]
    for key, label in labels:
        lines.append(f"| {label} | {len(groups[key])} | {sum(map(len, groups[key]))} |")
    for key, label in labels:
        lines.extend(["", f"## {label}", ""])
        emitted = 0
        for index, group in enumerate(groups[key]):
            group_lines = _markdown_group(group)
            if emitted + len(group_lines) > max_group_lines:
                lines.append(f"- ... truncated {len(groups[key]) - index} more groups. Use `--json` for the full report.")
                break
            lines.extend(group_lines)
            emitted += len(group_lines)
        if not groups[key]:
            lines.append("None.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    roots = [Path(value) for value in args.paths]
    inventory = scan_paths(
        roots,
        display_root=Path(args.root) if args.root else None,
        extensions=args.extensions,
        skip_dirs=args.skip_dir,
        include_oldversions=args.include_oldversions,
        include_vendor=True,
        include_staging=True,
        hash_files=not args.no_hash,
    )
    groups = legacy_groups(inventory.records)
    print(f"files scanned: {len(inventory.records)}")
    print(f"hash duplicate groups: {len(groups['hash_duplicates'])}")
    print(f"renamed hash duplicate groups: {len(groups['renamed_hash_duplicates'])}")
    print(f"same-name/same-size groups: {len(groups['same_name_same_size'])}")
    print(f"same-name/different-size groups: {len(groups['same_name_different_size'])}")
    for error in inventory.errors:
        print(f"warning: {error}", file=sys.stderr)

    if args.csv:
        _write_csv(Path(args.csv), inventory.records)
    if args.json:
        payload = {
            "root": str(inventory.root),
            "files": [_legacy_record(record) for record in inventory.records],
            "groups": _groups_to_json(groups),
        }
        Path(args.json).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.markdown:
        _write_markdown(
            Path(args.markdown),
            inventory.records,
            groups,
            inventory.root,
            args.max_group_lines,
        )
    return 0
