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

from pihti_dedup import __version__, inventor_session
from pihti_dedup.cache_root import CacheRootError, cache_root
from pihti_dedup.cleanup import execute_cleanup, plan_merge_exact_cleanup
from pihti_dedup.git_history import recent_pull_request_merges
from pihti_dedup.inventor_meta import INVENTOR_EXTENSIONS, read_document
from pihti_dedup.inventory import CAD_EXTENSIONS, scan_workspace
from pihti_dedup.notes_check import CATEGORY_ORDER, CATEGORY_TITLES, CheckResult, check_notes
from pihti_dedup.sidecar import SidecarError, seed_text, sidecar_path, write_sidecar

SEED_SAMPLE = 10


class WorkspaceError(ValueError):
    """The resolved workspace is not an Inventor project."""


def resolve_workspace(path: str) -> Path:
    """Resolve `path` and refuse it unless an Inventor project sits at its root.

    `UsingUniqueFilenames=Yes` makes the whole workspace fair game for every
    command below, so a folder picked by mistake (a home directory, say) must
    fail here, before anything is walked, rather than get scanned in full.
    Every workspace-taking subcommand goes through this one check.
    """

    workspace = Path(path).resolve()
    if not any(workspace.glob("*.ipj")):
        raise WorkspaceError(
            f"{workspace} is not an Inventor workspace (no .ipj file here); "
            "pass the PIHTI folder"
        )
    return workspace


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

    serve = subparsers.add_parser("serve", help="Run the local CAD viewer")
    serve.add_argument("workspace", nargs="?", default=".")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=4185)
    serve.add_argument("--open", action="store_true", help="Open the viewer in the default browser")
    serve.add_argument(
        "--refresh-seconds",
        type=float,
        default=5.0,
        help="Background snapshot refresh period; 0 validates the disk on every request",
    )

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

    standard = subparsers.add_parser(
        "standard-parts",
        help="Preview or move standard fasteners into ContentCenter/Fastners",
    )
    standard.add_argument("workspace", nargs="?", default=".")
    standard_mode = standard.add_mutually_exclusive_group(required=True)
    standard_mode.add_argument("--dry", action="store_true", help="Print the candidate table only")
    standard_mode.add_argument(
        "--apply", action="store_true", help="Move every candidate whose outcome is 'move'"
    )
    standard.add_argument(
        "--references-checked",
        action="store_true",
        help="Confirm the referring assemblies were reviewed",
    )
    standard.add_argument("--json", metavar="PATH", help="Write the plan or result as JSON")

    warm = subparsers.add_parser(
        "warm-previews", help="Render and disk-cache STL, STEP, 3MF, and DWG previews"
    )
    warm.add_argument("workspace", nargs="?", default=".")
    warm.add_argument("--include-vendor", action="store_true")
    warm.add_argument("--quiet", action="store_true", help="Counts only, no per-file progress")
    warm.add_argument(
        "--meshes",
        action="store_true",
        help="Also build the inspector's 3D meshes for STL, 3MF, and STEP files",
    )
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

    rename = subparsers.add_parser(
        "rename",
        help="Rename one Inventor document in place and record it in the rename ledger",
        description=(
            "Rename one Inventor document in place and record it in the rename ledger. "
            "With --repair, the running Inventor opens every referring document first, "
            "repoints it to the new file, saves it, and verifies it on reopen. Exit status "
            "1 means the rename happened but not every referrer was repaired."
        ),
    )
    rename.add_argument("relative_path", help="Workspace-relative path of the file to rename")
    rename.add_argument("new_name", help="New filename; the extension is kept")
    rename.add_argument("workspace", nargs="?", default=".")
    rename.add_argument(
        "--repair",
        action="store_true",
        help="Repoint and save the referring documents through the running Inventor",
    )
    rename.add_argument(
        "--dry", action="store_true", help="Print the plan only; nothing is renamed or saved"
    )
    rename.add_argument(
        "--confirm-collision",
        action="store_true",
        help="Proceed although another file still carries the old name",
    )

    notes = subparsers.add_parser("notes", help="Lint folder notes, sidecars, and sourcing notes")
    notes_commands = notes.add_subparsers(dest="notes_command", required=True)
    notes_check = notes_commands.add_parser(
        "check",
        help="Read-only check for marker drift, missing summaries, bad sidecars, and bad sourcing notes",
    )
    notes_check.add_argument("workspace", nargs="?", default=".")
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


def _standard_parts(workspace: Path, *, apply: bool, references_checked: bool) -> tuple[int, dict]:
    """Print the standard-part table; with `apply`, carry out the plain moves.

    Only `move` outcomes run here. A copy already standing in the library is
    quarantined one confirmed row at a time from the viewer, never in bulk.
    """

    from pihti_dedup.standard_parts import (
        MOVE,
        StandardMoveError,
        execute_standard_move,
        find_standard_candidates,
    )
    from pihti_dedup.whereused import build_index, filename_locations

    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    inventory = scan_workspace(workspace, include_vendor=False, hash_files=False)
    candidates = find_standard_candidates(
        workspace,
        inventory.records,
        fields_for=lambda record: read_document(workspace / record.path).fields,
        index=build_index(workspace),
        locations=filename_locations(workspace),
    )
    print(f"workspace: {workspace}")
    print(f"standard-part candidates: {len(candidates)}")
    for candidate in candidates:
        plan = candidate.plan
        print(f"{plan.outcome.upper():<24} {_windows_path(candidate.path)}")
        print(f"  evidence: {'; '.join(candidate.evidence.labels)}")
        print(f"  destination: {_windows_path(plan.destination_path)}")
        print(f"  referring documents: {len(plan.referrers)}")
        if plan.reason and plan.outcome != MOVE:
            print(f"  {plan.reason}")
    payload: dict = {
        "dry_run": not apply,
        "candidates": [candidate.plan.to_dict() for candidate in candidates],
    }
    if not apply:
        print("DRY RUN — no files changed")
        return 0, payload
    if not references_checked:
        print("error: --apply requires --references-checked; nothing changed", file=sys.stderr)
        return 2, payload
    moved: list[dict] = []
    failures: list[str] = []
    for candidate in candidates:
        if candidate.plan.outcome != MOVE:
            continue
        try:
            result = execute_standard_move(workspace, candidate.plan, confirmed=True)
        except (StandardMoveError, OSError) as exc:
            failures.append(f"{candidate.path}: {exc}")
            continue
        moved.append({"path": candidate.path, "ledger_id": result.entry.id})
        print(
            f"MOVED {_windows_path(candidate.path)} -> "
            f"{_windows_path(candidate.plan.destination_path)} (ledger {result.entry.id})"
        )
    print(f"MOVED {len(moved)} files; open the referring assemblies once to confirm")
    for failure in failures:
        print(f"warning: {failure}", file=sys.stderr)
    payload.update(moved=moved, failures=failures)
    return (1 if failures else 0), payload


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
    print(f"cache root: {cache_root(workspace)}")
    print(f"preview cache: {geometry_preview.preview_store(workspace)}")

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


def _warm_meshes(workspace: Path, *, include_vendor: bool, quiet: bool) -> dict:
    """Build every missing inspector mesh, so the first 3D view is instant too."""

    from pihti_dedup import mesh_cache

    print(f"mesh cache: {mesh_cache.mesh_store(workspace)}")

    def report(index: int, total: int, path: str, state: str, seconds: float) -> None:
        print(f"[{index:>4}/{total}] {state:<9} {seconds:5.2f}s  {_windows_path(path)}", flush=True)

    result = mesh_cache.warm_meshes(
        workspace, include_vendor=include_vendor, progress=None if quiet else report
    )
    print(
        f"meshes: considered {result.considered} · built {result.rendered} · "
        f"already cached {result.cached} · failed {result.failed} in {result.seconds:.1f}s"
    )
    for failure in result.failures:
        print(f"warning: {failure}", file=sys.stderr)
    return result.to_dict()


def _relative(workspace: Path, path: Path | str) -> str:
    try:
        return _windows_path(Path(path).relative_to(workspace).as_posix())
    except ValueError:
        return str(path)


def _outcome_text(outcome: str) -> str:
    """A repair outcome as the CLI reports it; matches the dry-run wording."""

    if outcome == inventor_session.NO_DESCRIPTOR:
        return "uses another file with the old name"
    return outcome


def _rename(
    workspace: Path,
    relative_path: str,
    new_name: str,
    *,
    repair: bool,
    dry: bool,
    confirm_collision: bool,
) -> int:
    from pihti_dedup.renames import (
        RenameError,
        execute_rename,
        plan_rename,
        read_ledger,
        settled_pairs,
    )
    from pihti_dedup.whereused import build_index

    index = build_index(workspace, settled=settled_pairs(read_ledger(workspace)))
    try:
        plan = plan_rename(workspace, relative_path, new_name, index=index)
    except RenameError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"rename: {_windows_path(plan.old_path)} -> {plan.new_name}")
    print(f"referring documents: {len(plan.referrers)}")
    for referrer in plan.referrers:
        print(f"  {_windows_path(referrer)}")
    if plan.old_name_survivors:
        print(f"warning: {plan.old_name} still exists elsewhere; Inventor may rebind silently:")
        for survivor in plan.old_name_survivors:
            print(f"  {_windows_path(survivor)}")

    session = None
    if repair and plan.referrers:
        session = inventor_session.connect()
        if session is None:
            print(
                "error: Inventor is not running or not answering; nothing was renamed",
                file=sys.stderr,
            )
            return 2
        print(f"inventor: {session.version}")
    elif repair:
        print("inventor: no referring documents, nothing to repair")

    if dry:
        if session is not None:
            try:
                repair_plan = inventor_session.plan_repair(
                    session,
                    [workspace / referrer for referrer in plan.referrers],
                    plan.old_name,
                    target=workspace / plan.old_path,
                    survivors=[workspace / survivor for survivor in plan.old_name_survivors],
                )
            except inventor_session.SessionTimeout as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            if repair_plan.target_open:
                print(f"blocked: {plan.old_name} is {inventor_session.CLOSE_FIRST}")
            for item in repair_plan.referrers:
                print(f"  {_relative(workspace, item.path)}: {item.state}")
        print("DRY RUN: nothing renamed or saved")
        return 0

    if plan.needs_confirmation and not confirm_collision:
        print(
            "error: the old name survives elsewhere; pass --confirm-collision to proceed. "
            "Nothing was renamed.",
            file=sys.stderr,
        )
        return 2
    try:
        result = execute_rename(workspace, plan, confirmed=confirm_collision, session=session)
    except (RenameError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"RENAMED {_windows_path(plan.old_path)} -> {_windows_path(plan.new_path)}")
    if result.sidecar_moved:
        print(f"sidecar: {_windows_path(plan.sidecar_to or '')}")
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    entry = result.entry
    if result.repair is not None:
        indirect = {path.casefold() for path in entry.indirect}
        for path, outcome in result.repair.outcomes:
            relative = _relative(workspace, path)
            if relative.replace("\\", "/").casefold() in indirect:
                text = "holds the old name only indirectly; Inventor refreshes it on the next save"
            else:
                text = _outcome_text(outcome)
            print(f"  {relative}: {text}")
    print(f"ledger: {entry.id} settled={'yes' if entry.settled else 'no'}")
    if entry.repair_note:
        print(f"note: {entry.repair_note}")
    return 0 if result.repair is None or result.repair.complete else 1


def _print_notes_check(result: CheckResult) -> None:
    """Plain-text report, workspace-relative POSIX paths, no colours."""

    for category in CATEGORY_ORDER:
        items = result.in_category(category)
        if not items:
            continue
        print(f"{CATEGORY_TITLES[category]}:")
        for finding in items:
            print(f"  {finding.path}: {finding.detail}")
    print("notes check: clean" if result.clean else f"notes check: {len(result.findings)} findings")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = resolve_workspace(args.workspace)
    except WorkspaceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

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
        try:
            cache_root(workspace)
        except CacheRootError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        payload = _warm_previews(
            workspace, include_vendor=args.include_vendor, quiet=args.quiet
        )
        if args.meshes:
            meshes = _warm_meshes(
                workspace, include_vendor=args.include_vendor, quiet=args.quiet
            )
            payload = {**payload, "meshes": meshes}
        if args.json:
            Path(args.json).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        failed = payload["failures"] or payload.get("meshes", {}).get("failures")
        return 1 if failed else 0

    if args.command == "meta":
        payload = _seed_sidecars(workspace, include_vendor=args.include_vendor, apply=args.apply)
        if args.json:
            Path(args.json).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        return 1 if payload["failures"] else 0

    if args.command == "standard-parts":
        code, payload = _standard_parts(
            workspace, apply=args.apply, references_checked=args.references_checked
        )
        if args.json:
            Path(args.json).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        return code

    if args.command == "rename":
        return _rename(
            workspace,
            args.relative_path,
            args.new_name,
            repair=args.repair,
            dry=args.dry,
            confirm_collision=args.confirm_collision,
        )

    if args.command == "notes":
        result = check_notes(workspace)
        _print_notes_check(result)
        return 0 if result.clean else 1

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

    url = f"http://{args.host}:{args.port}/catalog"
    try:
        app = create_app(workspace, refresh_seconds=max(args.refresh_seconds, 0.0))
    except CacheRootError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.open:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    print(f"PIHTI CAD viewer: {url}")
    print(f"preview and mesh cache: {cache_root(workspace)}")
    app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)
    return 0
