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
from pihti_dedup.inventor_meta import INVENTOR_EXTENSIONS, read_document
from pihti_dedup.inventory import CAD_EXTENSIONS, scan_workspace
from pihti_dedup.sidecar import SidecarError, seed_text, sidecar_path, write_sidecar

SEED_SAMPLE = 10


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

    warm = subparsers.add_parser(
        "warm-previews", help="Render and disk-cache STL, STEP, 3MF, and DWG previews"
    )
    warm.add_argument("workspace", nargs="?", default=".")
    warm.add_argument("--include-vendor", action="store_true")
    warm.add_argument("--quiet", action="store_true", help="Counts only, no per-file progress")
    warm.add_argument("--json", metavar="PATH", help="Write the result as JSON")

    meta = subparsers.add_parser("meta", help="Metadata sidecars beside CAD files")
    meta_commands = meta.add_subparsers(dest="meta_command", required=True)
    seed = meta_commands.add_parser(
        "seed", help="Create missing sidecars from Inventor iProperties"
    )
    seed.add_argument("workspace", nargs="?", default=".")
    seed.add_argument("--include-vendor", action="store_true")
    seed_mode = seed.add_mutually_exclusive_group(required=True)
    seed_mode.add_argument("--dry", action="store_true", help="Count and sample only")
    seed_mode.add_argument("--apply", action="store_true", help="Write the missing sidecars")
    seed.add_argument("--json", metavar="PATH", help="Write the plan or result as JSON")
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


def _seed_sidecars(workspace: Path, *, include_vendor: bool, apply: bool) -> dict:
    """Seed sidecars for Inventor documents that do not have one yet.

    Only `.ipt`/`.iam`/`.idw`/`.ipn` are seeded in bulk: other CAD files carry no
    iProperties, so an automatic sidecar for them would be empty ceremony. This
    writes files and never touches Git.
    """

    inventory = scan_workspace(workspace, include_vendor=include_vendor, hash_files=False)
    targets = [
        record
        for record in inventory.records
        if Path(record.path).suffix.casefold() in INVENTOR_EXTENSIONS
    ]
    missing = [record for record in targets if not sidecar_path(workspace / record.path).exists()]
    print(f"workspace: {workspace}")
    print(f"Inventor documents: {len(targets)}")
    print(f"existing sidecars: {len(targets) - len(missing)}")
    print(f"missing sidecars: {len(missing)}")

    written: list[str] = []
    failures: list[str] = []
    if apply:
        for record in missing:
            path = workspace / record.path
            try:
                write_sidecar(sidecar_path(path), seed_text(read_document(path).fields))
            except (SidecarError, OSError) as exc:
                failures.append(f"{record.path}: {exc}")
                continue
            written.append(f"{record.path}.md")
        print(f"SEEDED {len(written)} sidecars")
        for failure in failures:
            print(f"warning: {failure}", file=sys.stderr)
    else:
        print("DRY RUN — no files written")
        for record in missing[:SEED_SAMPLE]:
            print(f"WOULD SEED {_windows_path(record.path)}.md")
        if len(missing) > SEED_SAMPLE:
            print(f"... and {len(missing) - SEED_SAMPLE} more")

    return {
        "dry_run": not apply,
        "documents": len(targets),
        "missing": [record.path for record in missing],
        "written": written,
        "failures": failures,
    }


def _warm_previews(workspace: Path, *, include_vendor: bool, quiet: bool) -> dict:
    """Build every missing geometry preview so the next catalog visit is instant.

    A cold whole-workspace build costs minutes, almost all of it STEP parsing,
    so this exists as a command rather than as something a page visit triggers.
    """

    from pihti_dedup import geometry_preview

    drawable = sorted(geometry_preview.available_extensions())
    print(f"workspace: {workspace}")
    print(f"renderable extensions: {', '.join(drawable) if drawable else 'none'}")
    missing = geometry_preview.missing_extra()
    if not drawable:
        print(
            f"error: nothing can be rendered; reinstall with the '{missing}' extra",
            file=sys.stderr,
        )
        return geometry_preview.WarmResult().to_dict()
    if missing:
        print(f"note: the '{missing}' extra is absent, so some formats are skipped")
    print(f"cache: {_windows_path(str(geometry_preview.preview_store(workspace)))}")

    def report(index: int, total: int, path: str, state: str, seconds: float) -> None:
        print(f"[{index:>4}/{total}] {state:<8} {seconds:5.2f}s  {_windows_path(path)}", flush=True)

    result = geometry_preview.warm_previews(
        workspace,
        include_vendor=include_vendor,
        progress=None if quiet else report,
    )
    print(
        f"considered {result.considered} · rendered {result.rendered} · "
        f"already cached {result.cached} · failed {result.failed} "
        f"in {result.seconds:.1f}s"
    )
    for failure in result.failures:
        print(f"warning: {failure}", file=sys.stderr)
    return result.to_dict()


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

    if args.command == "warm-previews":
        payload = _warm_previews(
            workspace, include_vendor=args.include_vendor, quiet=args.quiet
        )
        if args.json:
            Path(args.json).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        return 1 if payload["failures"] else 0

    if args.command == "meta":
        payload = _seed_sidecars(workspace, include_vendor=args.include_vendor, apply=args.apply)
        if args.json:
            Path(args.json).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        return 1 if payload["failures"] else 0

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
