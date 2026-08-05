"""Command-line interface for scanning and serving the duplicate viewer."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Sequence

from pihti_dedup import __version__
from pihti_dedup.cleanup import execute_cleanup, plan_merge_exact_cleanup
from pihti_dedup.git_history import recent_pull_request_merges
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

    cleanup = subparsers.add_parser(
        "merge-cleanup", help="Preview or quarantine exact copies added by a merged PR"
    )
    cleanup.add_argument("workspace", nargs="?", default=".")
    cleanup.add_argument("--pr", type=int, required=True, help="Merged pull-request number")
    cleanup.add_argument("--include-vendor", action="store_true")
    mode = cleanup.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry", action="store_true", help="Print the complete plan only")
    mode.add_argument("--apply", action="store_true", help="Move the planned files to quarantine")
    cleanup.add_argument(
        "--references-checked",
        action="store_true",
        help="Confirm Inventor/Design Assistant references were reviewed",
    )
    cleanup.add_argument("--json", metavar="PATH", help="Write the plan or result as JSON")
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


def _windows_path(value: str) -> str:
    return value.replace("/", "\\")


def _modified_time(value: int) -> str:
    return (
        datetime.fromtimestamp(value / 1_000_000_000).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    )


def _print_cleanup_plan(plan) -> None:
    print("DRY RUN plan — no files changed")
    print(f"PR #{plan.pr_number}: {plan.branch}")
    print(f"merge-added exact-copy candidates: {len(plan.candidates)}")
    print(f"protected all-merge groups: {plan.protected_groups}")
    for candidate in plan.candidates:
        print(
            f"WOULD QUARANTINE {_windows_path(candidate.path)} "
            f"(modified {_modified_time(candidate.mtime_ns)})"
        )
        for keep_path in candidate.keep_paths:
            print(f"  KEEP {_windows_path(keep_path)}")


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

    if args.command == "merge-cleanup":
        merge = next(
            (item for item in recent_pull_request_merges(workspace) if item.number == args.pr),
            None,
        )
        if merge is None:
            print(
                f"error: merged PR #{args.pr} was not found in local first-parent history",
                file=sys.stderr,
            )
            return 2
        inventory = scan_workspace(workspace, include_vendor=args.include_vendor)
        plan = plan_merge_exact_cleanup(inventory, merge)
        _print_cleanup_plan(plan)
        payload = plan.to_dict()
        if args.apply:
            if not args.references_checked:
                print(
                    "error: --apply requires --references-checked; nothing changed",
                    file=sys.stderr,
                )
                return 2
            execution = execute_cleanup(workspace, plan, references_checked=args.references_checked)
            rescanned = scan_workspace(workspace, include_vendor=args.include_vendor)
            remaining = {record.path.casefold() for record in rescanned.records}
            if any(path.casefold() in remaining for path in execution.moved):
                print("error: post-cleanup scan still found a quarantined path", file=sys.stderr)
                return 1
            payload = {
                "plan": plan.to_dict(),
                "execution": execution.to_dict(),
                "post_scan": rescanned.summary,
            }
            print(f"QUARANTINED {len(execution.moved)} files")
            if execution.manifest:
                print(f"manifest: {_windows_path(execution.manifest)}")
                print(
                    "required: open affected top-level assemblies in Inventor and verify resolution"
                )
        if args.json:
            Path(args.json).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        return 0

    from pihti_dedup.web import create_app

    url = f"http://{args.host}:{args.port}/duplicates"
    if args.open:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    print(f"PIHTI duplicate viewer: {url}")
    create_app(workspace).run(host=args.host, port=args.port, threaded=True, use_reloader=False)
    return 0
