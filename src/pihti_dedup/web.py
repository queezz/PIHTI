"""Flask application for local duplicate review and guarded quarantine."""

from __future__ import annotations

import ipaddress
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from flask import Flask, jsonify, render_template, request

from pihti_dedup import __version__
from pihti_dedup.cleanup import (
    execute_cleanup,
    execute_member_cleanup,
    plan_member_cleanup,
    plan_merge_exact_cleanup,
)
from pihti_dedup.git_history import PullRequestMerge, recent_pull_request_merges
from pihti_dedup.inventory import Inventory, scan_workspace

Scanner = Callable[..., Inventory]
MergeReader = Callable[[Path], tuple[PullRequestMerge, ...]]


class InventoryCache:
    """Small process-local cache so HTML and JSON views can share one scan."""

    def __init__(self, workspace: Path, scanner: Scanner, max_age: float = 10.0) -> None:
        self.workspace = workspace
        self.scanner = scanner
        self.max_age = max_age
        self._lock = threading.Lock()
        self._entries: dict[bool, tuple[float, Inventory]] = {}

    def get(self, *, include_vendor: bool, force: bool = False) -> Inventory:
        with self._lock:
            cached = self._entries.get(include_vendor)
            if cached and not force and time.monotonic() - cached[0] <= self.max_age:
                return cached[1]
            inventory = self.scanner(self.workspace, include_vendor=include_vendor)
            self._entries[include_vendor] = (time.monotonic(), inventory)
            return inventory

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


def _flag(value: str | None) -> bool:
    return (value or "").casefold() in {"1", "true", "yes", "on"}


def _filesize(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size):,} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value:,} B"


def _windows_path(value: str) -> str:
    return value.replace("/", "\\")


def _filetime(value: int) -> str:
    return datetime.fromtimestamp(value / 1_000_000_000).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _is_newver_name(value: str) -> bool:
    return Path(value).stem.casefold().endswith(".newver")


def _is_loopback(address: str | None) -> bool:
    try:
        return ipaddress.ip_address(address or "").is_loopback
    except ValueError:
        return False


def create_app(
    workspace: Path | str | None = None,
    *,
    scanner: Scanner = scan_workspace,
    merge_reader: MergeReader = recent_pull_request_merges,
) -> Flask:
    root = Path(workspace or Path.cwd()).resolve()
    app = Flask(__name__)
    app.config.update(WORKSPACE=root, VERSION=__version__, FORM_TOKEN=secrets.token_urlsafe(32))
    cache = InventoryCache(root, scanner)
    app.extensions["pihti_inventory_cache"] = cache
    app.jinja_env.filters["filesize"] = _filesize
    app.jinja_env.filters["winpath"] = _windows_path
    app.jinja_env.filters["filetime"] = _filetime
    app.jinja_env.tests["newver_name"] = _is_newver_name

    @app.after_request
    def no_store(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    @app.get("/duplicates")
    def duplicates():
        return render_template("duplicates.html", workspace=root.name, version=__version__)

    @app.get("/duplicates/results")
    def duplicates_results():
        include_vendor = _flag(request.args.get("include_vendor"))
        force = _flag(request.args.get("refresh"))
        try:
            inventory = cache.get(include_vendor=include_vendor, force=force)
        except Exception as exc:  # a local scan failure should stay visible in the shell
            return render_template("_scan_error.html", message=str(exc)), 500
        folder_stats = []
        for system in sorted({record.system for record in inventory.records}, key=str.casefold):
            matching = [group for group in inventory.groups if system in group.systems]
            folder_stats.append(
                {
                    "name": system,
                    "groups": len(matching),
                    "collisions": sum(group.kind == "collision" for group in matching),
                }
            )

        merge_views = []
        group_merges: dict[str, list[str]] = {group.id: [] for group in inventory.groups}
        for merge in merge_reader(root):
            matching = [
                group
                for group in inventory.groups
                if any(record.path in merge.paths for record in group.records)
            ]
            merge_key = str(merge.number)
            for group in matching:
                group_merges[group.id].append(merge_key)
            cleanup_plan = plan_merge_exact_cleanup(inventory, merge)
            merge_views.append(
                {
                    "key": merge_key,
                    "number": merge.number,
                    "branch": merge.branch.rsplit("/", 1)[-1],
                    "cad_files": merge.cad_files,
                    "folders": merge.folders,
                    "groups": len(matching),
                    "collisions": sum(group.kind == "collision" for group in matching),
                    "cleanup_candidates": len(cleanup_plan.candidates),
                }
            )
        extensions = sorted({suffix for group in inventory.groups for suffix in group.extensions})
        member_plans = {}
        for group in inventory.groups:
            if group.kind not in {"exact", "renamed"}:
                continue
            for record in group.records:
                try:
                    plan = plan_member_cleanup(inventory, group_id=group.id, path=record.path)
                except ValueError:
                    continue
                member_plans[(group.id, record.path)] = plan.to_dict()
        return render_template(
            "_results.html",
            inventory=inventory,
            folder_stats=folder_stats,
            merge_views=merge_views,
            group_merges=group_merges,
            extensions=extensions,
            member_plans=member_plans,
            form_token=app.config["FORM_TOKEN"],
        )

    @app.get("/duplicates/merge-plan/<int:pr_number>")
    def merge_cleanup_plan(pr_number: int):
        merge = next(
            (item for item in merge_reader(root) if item.number == pr_number),
            None,
        )
        if merge is None:
            return jsonify({"error": f"merged PR #{pr_number} was not found"}), 404
        include_vendor = _flag(request.args.get("include_vendor"))
        inventory = cache.get(include_vendor=include_vendor)
        return jsonify(plan_merge_exact_cleanup(inventory, merge).to_dict())

    @app.post("/duplicates/merge-plan/<int:pr_number>/apply")
    def merge_cleanup_apply(pr_number: int):
        if not _is_loopback(request.remote_addr):
            return jsonify({"error": "cleanup is restricted to localhost"}), 403
        if not secrets.compare_digest(
            request.headers.get("X-PIHTI-Token", ""), app.config["FORM_TOKEN"]
        ):
            return jsonify({"error": "invalid form token"}), 403
        payload = request.get_json(silent=True) or {}
        if payload.get("references_checked") is not True:
            return jsonify({"error": "Inventor references must be checked first"}), 400
        merge = next(
            (item for item in merge_reader(root) if item.number == pr_number),
            None,
        )
        if merge is None:
            return jsonify({"error": f"merged PR #{pr_number} was not found"}), 404
        include_vendor = bool(payload.get("include_vendor"))
        inventory = cache.get(include_vendor=include_vendor, force=True)
        plan = plan_merge_exact_cleanup(inventory, merge)
        if not secrets.compare_digest(str(payload.get("signature", "")), plan.signature):
            return jsonify({"error": "cleanup plan changed; run the dry preview again"}), 409
        try:
            execution = execute_cleanup(root, plan, references_checked=True)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        cache.clear()
        refreshed = cache.get(include_vendor=include_vendor, force=True)
        return jsonify({"execution": execution.to_dict(), "post_scan": refreshed.summary})

    @app.post("/duplicates/member/<group_id>/delete")
    def member_cleanup_apply(group_id: str):
        if not _is_loopback(request.remote_addr):
            return jsonify({"error": "cleanup is restricted to localhost"}), 403
        if not secrets.compare_digest(
            request.headers.get("X-PIHTI-Token", ""), app.config["FORM_TOKEN"]
        ):
            return jsonify({"error": "invalid form token"}), 403
        payload = request.get_json(silent=True) or {}
        if payload.get("references_checked") is not True:
            return jsonify({"error": "Inventor references must be checked first"}), 400
        path = str(payload.get("path", ""))
        include_vendor = bool(payload.get("include_vendor"))
        inventory = cache.get(include_vendor=include_vendor, force=True)
        try:
            plan = plan_member_cleanup(inventory, group_id=group_id, path=path)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        if not secrets.compare_digest(str(payload.get("signature", "")), plan.signature):
            return jsonify({"error": "cleanup member changed; rescan and try again"}), 409
        try:
            execution = execute_member_cleanup(root, plan, references_checked=True)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        cache.clear()
        refreshed = cache.get(include_vendor=include_vendor, force=True)
        return jsonify({"execution": execution.to_dict(), "post_scan": refreshed.summary})

    @app.get("/duplicates/data")
    def duplicates_data():
        include_vendor = _flag(request.args.get("include_vendor"))
        force = _flag(request.args.get("refresh"))
        inventory = cache.get(include_vendor=include_vendor, force=force)
        return jsonify(inventory.to_dict())

    @app.get("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "service": "pihti-dedup",
                "version": __version__,
                "workspace": root.name,
                "read_only": False,
                "cleanup_mode": "recoverable-quarantine",
            }
        )

    return app
