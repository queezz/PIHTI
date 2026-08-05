"""Flask application for local, read-only duplicate review."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

from flask import Flask, jsonify, render_template, request

from pihti_dedup import __version__
from pihti_dedup.inventory import Inventory, scan_workspace

Scanner = Callable[..., Inventory]


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


def create_app(workspace: Path | str | None = None, *, scanner: Scanner = scan_workspace) -> Flask:
    root = Path(workspace or Path.cwd()).resolve()
    app = Flask(__name__)
    app.config.update(WORKSPACE=root, VERSION=__version__)
    cache = InventoryCache(root, scanner)
    app.extensions["pihti_inventory_cache"] = cache
    app.jinja_env.filters["filesize"] = _filesize

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
        systems = sorted(
            {system for group in inventory.groups for system in group.systems}, key=str.casefold
        )
        extensions = sorted({suffix for group in inventory.groups for suffix in group.extensions})
        return render_template(
            "_results.html",
            inventory=inventory,
            systems=systems,
            extensions=extensions,
        )

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
                "read_only": True,
            }
        )

    return app
