"""Command-line interface for scanning and serving the duplicate viewer."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Sequence

from pihti_dedup import __version__
from pihti_dedup.inventory import CAD_EXTENSIONS, scan_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pihti-dedup", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan and summarize duplicate groups")
    scan.add_argument("workspace", nargs="?", default=".")
    scan.add_argument("--include-vendor", action="store_true")
    scan.add_argument("--all-files", action="store_true", help="Scan every suffix, not only CAD")
    scan.add_argument("--no-hash", action="store_true")
    scan.add_argument("--json", metavar="PATH", help="Write the portable inventory as JSON")

    serve = subparsers.add_parser("serve", help="Run the local duplicate viewer")
    serve.add_argument("workspace", nargs="?", default=".")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=4185)
    serve.add_argument("--open", action="store_true", help="Open the viewer in the default browser")
    return parser


def _print_summary(inventory) -> None:
    summary = inventory.summary
    print(f"workspace: {inventory.root}")
    print(f"CAD files scanned: {summary['files']}")
    print(f"same-filename groups: {summary['filename_groups']}")
    print(f"same-name/different-hash collisions: {summary['collision_groups']}")
    print(f"same-name/exact-copy groups: {summary['exact_groups']}")
    print(f"same-name/unverified groups: {summary['unverified_groups']}")
    print(f"different-name/exact-copy groups: {summary['renamed_groups']}")
    print(f"excluded paths: {summary['excluded_paths']}")
    if inventory.errors:
        for error in inventory.errors:
            print(f"warning: {error}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = Path(args.workspace).resolve()

    if args.command == "scan":
        extensions = None if args.all_files else CAD_EXTENSIONS
        inventory = scan_workspace(
            workspace,
            include_vendor=args.include_vendor,
            hash_files=not args.no_hash,
            extensions=extensions,
        )
        _print_summary(inventory)
        if args.json:
            Path(args.json).write_text(
                json.dumps(inventory.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return 0

    from pihti_dedup.web import create_app

    url = f"http://{args.host}:{args.port}/duplicates"
    if args.open:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    print(f"PIHTI duplicate viewer: {url}")
    create_app(workspace).run(host=args.host, port=args.port, threaded=True, use_reloader=False)
    return 0
