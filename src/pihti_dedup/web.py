"""Flask application for local duplicate review, catalog, and guarded quarantine."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import secrets
import threading
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Callable

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for
from markupsafe import escape

from pihti_dedup import __version__
from pihti_dedup.cleanup import (
    execute_cleanup,
    execute_member_cleanup,
    plan_member_cleanup,
    plan_merge_exact_cleanup,
)
from pihti_dedup.foldernote import FolderNoteError, read_folder_note, write_folder_note
from pihti_dedup.git_history import PullRequestMerge, recent_pull_request_merges
from pihti_dedup.inventor_meta import INVENTOR_EXTENSIONS, DocumentMeta, Preview, read_preview
from pihti_dedup.inventor_meta import read_document as read_inventor_document
from pihti_dedup.inventory import Inventory, scan_workspace
from pihti_dedup.renames import (
    LEDGER_RELATIVE,
    RENAMEABLE_EXTENSIONS,
    RenameError,
    execute_rename,
    plan_rename,
    read_ledger,
    set_settled,
)
from pihti_dedup.sidecar import SidecarError, read_sidecar, seed_text, sidecar_path, write_sidecar
from pihti_dedup.whereused import ReferenceCache, build_index, filename_locations

Scanner = Callable[..., Inventory]
MergeReader = Callable[[Path], tuple[PullRequestMerge, ...]]

IPROPERTY_ROWS = (
    ("part_number", "Part number"),
    ("description", "Description"),
    ("material", "Material"),
    ("designer", "Designer"),
    ("author", "Author"),
    ("project", "Project"),
    ("vendor", "Vendor"),
    ("stock_number", "Stock number"),
    ("creation_time", "Created"),
    ("doc_subtype_name", "Document subtype"),
    ("last_updated_with", "Last updated with"),
    ("appearance", "Appearance"),
)
MASS_ROWS = (
    ("mass", "Mass", "g"),
    ("volume", "Volume", "cm³"),
    ("density", "Density", "g/cm³"),
    ("surface_area", "Surface area", "cm²"),
)


class InventoryCache:
    """Small process-local cache so HTML and JSON views can share one scan."""

    def __init__(self, workspace: Path, scanner: Scanner, max_age: float = 10.0) -> None:
        self.workspace = workspace
        self.scanner = scanner
        self.max_age = max_age
        self._lock = threading.Lock()
        self._entries: dict[tuple[bool, bool], tuple[float, Inventory]] = {}

    def get(
        self, *, include_vendor: bool, hash_files: bool = True, force: bool = False
    ) -> Inventory:
        key = (include_vendor, hash_files)
        with self._lock:
            cached = self._entries.get(key)
            if cached and not force and time.monotonic() - cached[0] <= self.max_age:
                return cached[1]
            inventory = self.scanner(
                self.workspace, include_vendor=include_vendor, hash_files=hash_files
            )
            self._entries[key] = (time.monotonic(), inventory)
            return inventory

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class PreviewCache:
    """Embedded previews keyed by path and modification time.

    Parsing a document costs a few milliseconds, but a catalog page asks for
    hundreds of previews at once and re-asks on every visit. Misses are cached
    too, so the handful of STEP-imported parts without a preview stay cheap.
    """

    def __init__(self, limit: int = 512) -> None:
        self.limit = limit
        self._lock = threading.Lock()
        self._entries: OrderedDict[tuple[str, int], Preview | None] = OrderedDict()

    def get(self, path: Path, mtime_ns: int) -> Preview | None:
        key = (os.path.normcase(str(path)), mtime_ns)
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key]
        preview = read_preview(path) if path.suffix.casefold() in INVENTOR_EXTENSIONS else None
        with self._lock:
            self._entries[key] = preview
            self._entries.move_to_end(key)
            while len(self._entries) > self.limit:
                self._entries.popitem(last=False)
        return preview


def placeholder_svg(suffix: str) -> str:
    """Neutral inline placeholder for a file that carries no embedded preview."""

    label = escape(suffix.lstrip(".").upper()[:5] or "FILE")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 120" role="img" '
        'aria-label="No embedded preview">'
        '<rect width="160" height="120" fill="#101822"/>'
        '<rect x="0.5" y="0.5" width="159" height="119" fill="none" stroke="#283747"/>'
        '<path d="M52 40h34l22 22v38H52z" fill="none" stroke="#3b4d61" stroke-width="2"/>'
        '<path d="M86 40v22h22" fill="none" stroke="#3b4d61" stroke-width="2"/>'
        f'<text x="80" y="86" fill="#697989" font-family="ui-monospace, monospace" '
        f'font-size="13" text-anchor="middle">{label}</text>'
        "</svg>"
    )


def _contained(root: Path, relative_path: str) -> Path | None:
    candidate = (relative_path or "").replace("\\", "/").strip()
    if not candidate or candidate.startswith("/"):
        return None
    try:
        resolved = (root / candidate).resolve()
    except (OSError, ValueError):
        return None
    if not resolved.is_relative_to(root) or resolved == root:
        return None
    return resolved


def workspace_file(root: Path, relative_path: str) -> Path | None:
    """Resolve a repo-relative path inside the workspace, or None if it escapes.

    Traversal, absolute paths, drive letters, and symlinks leaving the workspace
    all fail the containment check after resolution.
    """

    resolved = _contained(root, relative_path)
    return resolved if resolved is not None and resolved.is_file() else None


def workspace_folder(root: Path, relative_path: str) -> Path | None:
    """Same containment rule for a directory.

    The workspace root itself is refused: its `README.md` is the repository's
    front door, not a folder note.
    """

    resolved = _contained(root, relative_path)
    return resolved if resolved is not None and resolved.is_dir() else None


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


def _anchor(name: str) -> str:
    """A stable fragment id for a folder path, safe in a URL and unique.

    The slug alone would collide (`a/b` and `a-b`), so a short digest of the
    real path settles it; the readable part is kept for a usable address bar.
    """

    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:6]
    return f"{slug[:48]}-{digest}" if slug else digest


def _tree_list(store: dict) -> list[dict]:
    return [
        {**node, "children": _tree_list(node["children"])}
        for node in sorted(store.values(), key=lambda item: item["name"].casefold())
    ]


def folder_tree(folders: list[dict]) -> list[dict]:
    """Nest the flat catalog folder list into a tree with aggregate counts.

    A flat rail of 99 folders buries the scan card and cannot be skimmed, and
    the owner rejected an inner scrollbar as the fix. A tree shows the handful
    of top-level systems, each carrying the file count of its whole subtree, and
    opens only where asked.
    """

    roots: dict[str, dict] = {}
    for folder in folders:
        parts = folder["name"].split("/") if folder["name"] != "." else ["."]
        store = roots
        walked: list[str] = []
        node: dict | None = None
        for part in parts:
            walked.append(part)
            path = "/".join(walked)
            node = store.setdefault(
                part,
                {
                    "name": part,
                    "path": path,
                    "key": _anchor(path),
                    "count": 0,
                    "anchor": None,
                    "children": {},
                },
            )
            node["count"] += len(folder["files"])
            store = node["children"]
        if node is not None:
            node["anchor"] = folder["anchor"]
    return _tree_list(roots)


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
    previews = PreviewCache()
    references = ReferenceCache()
    app.extensions["pihti_inventory_cache"] = cache
    app.extensions["pihti_preview_cache"] = previews
    app.extensions["pihti_reference_cache"] = references
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

    @app.get("/preview/<path:relative_path>")
    def preview_image(relative_path: str):
        target = workspace_file(root, relative_path)
        if target is None:
            return Response("no such workspace file", status=404, mimetype="text/plain")
        try:
            preview = previews.get(target, target.stat().st_mtime_ns)
        except OSError:
            preview = None
        if preview is None:
            return Response(placeholder_svg(target.suffix), mimetype="image/svg+xml")
        return Response(preview.data, mimetype=preview.media_type)

    @app.get("/catalog")
    def catalog():
        include_vendor = _flag(request.args.get("include_vendor"))
        inventory = cache.get(include_vendor=include_vendor, hash_files=False)
        folders = _catalog_folders(inventory)
        return render_template(
            "catalog.html",
            version=__version__,
            inventory=inventory,
            folders=folders,
            tree=folder_tree(folders),
            file_count=len(inventory.records),
            form_token=app.config["FORM_TOKEN"],
            saved=_flag(request.args.get("saved")),
        )

    @app.get("/folder/<path:relative_folder>")
    def folder_page(relative_folder: str):
        target = workspace_folder(root, relative_folder)
        if target is None:
            return render_template(
                "_not_found.html", version=__version__, path=relative_folder
            ), 404
        return render_template("folder.html", **_folder_context(target))

    @app.post("/folder/<path:relative_folder>/note")
    def folder_note(relative_folder: str):
        guard = _guard(request)
        if guard is not None:
            return guard
        target = workspace_folder(root, relative_folder)
        if target is None:
            return render_template(
                "_not_found.html", version=__version__, path=relative_folder
            ), 404
        text = request.form.get("text", "")
        try:
            write_folder_note(target, text)
        except FolderNoteError as exc:
            context = _folder_context(target)
            context.update(error=str(exc), draft=text)
            return render_template("folder.html", **context), 400
        except OSError as exc:
            context = _folder_context(target)
            context.update(error=f"could not write the folder note: {exc}", draft=text)
            return render_template("folder.html", **context), 500
        relative = target.relative_to(root).as_posix()
        if request.form.get("origin") == "catalog":
            return redirect(url_for("catalog", saved="1") + f"#folder-note-{_anchor(relative)}")
        return redirect(url_for("folder_page", relative_folder=relative, saved="1"))

    @app.post("/part/<path:relative_path>/rename")
    def part_rename(relative_path: str):
        guard = _guard(request)
        if guard is not None:
            return guard
        target = workspace_file(root, relative_path)
        if target is None:
            return render_template("_not_found.html", version=__version__, path=relative_path), 404
        new_name = request.form.get("new_name", "")
        confirmed = _flag(request.form.get("confirm_collision"))
        index = build_index(root, cache=references)
        try:
            plan = plan_rename(
                root,
                target.relative_to(root).as_posix(),
                new_name,
                index=index,
                locations=filename_locations(root),
            )
        except RenameError as exc:
            context = _part_context(target)
            context.update(rename_error=str(exc), rename_draft=new_name)
            return render_template("part.html", **context), 400
        if plan.needs_confirmation and not confirmed:
            context = _part_context(target)
            context.update(rename_pending=plan, rename_draft=plan.new_name)
            return render_template("part.html", **context), 409
        try:
            result = execute_rename(root, plan, confirmed=confirmed)
        except (RenameError, OSError) as exc:
            context = _part_context(target)
            context.update(rename_error=str(exc), rename_draft=new_name)
            return render_template("part.html", **context), 409
        cache.clear()
        return redirect(url_for("part_page", relative_path=result.entry.new_path, renamed="1"))

    @app.get("/renames")
    def renames():
        entries = list(reversed(read_ledger(root)))
        views = [_rename_view(entry) for entry in entries]
        return render_template(
            "renames.html",
            version=__version__,
            workspace=root.name,
            entries=views,
            open_count=sum(not entry.settled for entry in entries),
            prompt_count=sum(entry.will_prompt and not entry.settled for entry in entries),
            ledger=LEDGER_RELATIVE,
            form_token=app.config["FORM_TOKEN"],
        )

    @app.post("/renames/<entry_id>/settled")
    def rename_settled(entry_id: str):
        if not _is_loopback(request.remote_addr):
            return jsonify({"error": "the ledger is restricted to localhost"}), 403
        if not secrets.compare_digest(
            request.headers.get("X-PIHTI-Token", ""), app.config["FORM_TOKEN"]
        ):
            return jsonify({"error": "invalid form token"}), 403
        payload = request.get_json(silent=True) or {}
        try:
            entry = set_settled(root, entry_id, bool(payload.get("settled")))
        except RenameError as exc:
            return jsonify({"error": str(exc)}), 404
        except OSError as exc:
            return jsonify({"error": f"could not write the ledger: {exc}"}), 500
        return jsonify({"id": entry.id, "settled": entry.settled})

    def _guard(current) -> Response | None:
        if not _is_loopback(current.remote_addr):
            return Response("editing is restricted to localhost", status=403)
        supplied = current.headers.get("X-PIHTI-Token") or current.form.get("token", "")
        if not secrets.compare_digest(supplied, app.config["FORM_TOKEN"]):
            return Response("invalid form token", status=403)
        return None

    def _catalog_folders(inventory: Inventory) -> list[dict]:
        folders = []
        for name, records in _folders(inventory):
            note = None
            try:
                note = read_folder_note(root / name) if name != "." else None
            except FolderNoteError:
                note = None
            key = _anchor(name)
            leaf = name.rsplit("/", 1)[-1]
            folders.append(
                {
                    "name": name,
                    "key": key,
                    "anchor": f"folder-{key}",
                    "note_anchor": f"folder-note-{key}",
                    "files": records,
                    "note": note,
                    "note_text": note.text if note else "",
                    "note_default": f"# {leaf}\n\nWhat this folder is for.\n",
                    "excerpt": note.excerpt if note else "",
                    "editable": name != ".",
                }
            )
        return folders

    def _folder_context(target: Path) -> dict:
        relative = target.relative_to(root).as_posix()
        inventory = cache.get(include_vendor=True, hash_files=False)
        prefix = f"{relative}/"
        files = [record for record in inventory.records if record.path.rsplit("/", 1)[0] == relative]
        subtree = [record for record in inventory.records if record.path.startswith(prefix)]
        error = None
        try:
            note = read_folder_note(target)
        except FolderNoteError as exc:
            note = None
            error = str(exc)
        return {
            "version": __version__,
            "path": relative,
            "name": target.name,
            "parent": relative.rsplit("/", 1)[0] if "/" in relative else "",
            "files": files,
            "subtree_count": len(subtree),
            "note": note,
            "note_text": note.text if note else "",
            "form_token": app.config["FORM_TOKEN"],
            "saved": _flag(request.args.get("saved")),
            "error": error,
            "draft": None,
        }

    def _rename_view(entry) -> dict:
        return {
            "entry": entry,
            "full_path": str(root / entry.new_path),
            "folder_path": str((root / entry.new_path).parent),
            "search": f"{entry.old_name} {entry.new_name} {entry.new_path}".casefold(),
        }

    @app.get("/part/<path:relative_path>")
    def part_page(relative_path: str):
        target = workspace_file(root, relative_path)
        if target is None:
            return render_template("_not_found.html", version=__version__, path=relative_path), 404
        return render_template("part.html", **_part_context(target))

    @app.post("/part/<path:relative_path>/metadata")
    def part_metadata(relative_path: str):
        if not _is_loopback(request.remote_addr):
            return Response("metadata editing is restricted to localhost", status=403)
        supplied = request.headers.get("X-PIHTI-Token") or request.form.get("token", "")
        if not secrets.compare_digest(supplied, app.config["FORM_TOKEN"]):
            return Response("invalid form token", status=403)
        target = workspace_file(root, relative_path)
        if target is None:
            return render_template("_not_found.html", version=__version__, path=relative_path), 404
        context = _part_context(target)
        if request.form.get("action") == "create":
            text = seed_text(context["meta"].fields)
        else:
            text = request.form.get("text", "")
        try:
            write_sidecar(sidecar_path(target), text)
        except SidecarError as exc:
            context.update(error=str(exc), draft=text)
            return render_template("part.html", **context), 400
        except OSError as exc:
            context.update(error=f"could not write the sidecar: {exc}", draft=text)
            return render_template("part.html", **context), 500
        return redirect(url_for("part_page", relative_path=context["path"], saved="1"))

    def _folders(inventory: Inventory) -> list[tuple[str, list]]:
        grouped: dict[str, list] = {}
        for record in inventory.records:
            parent = record.path.rsplit("/", 1)[0] if "/" in record.path else "."
            grouped.setdefault(parent, []).append(record)
        return sorted(grouped.items(), key=lambda item: item[0].casefold())

    def _part_context(target: Path) -> dict:
        relative = target.resolve().relative_to(root).as_posix()
        stat = target.stat()
        if target.suffix.casefold() in INVENTOR_EXTENSIONS:
            meta = read_inventor_document(target)
        else:
            meta = DocumentMeta(path=str(target), ok=False, error="not an Inventor document")
        properties = [
            (label, meta.fields[key]) for key, label in IPROPERTY_ROWS if meta.fields.get(key)
        ]
        valid_mass = meta.mass_properties()
        mass = [
            (label, valid_mass[key], unit)
            for key, label, unit in MASS_ROWS
            if key in valid_mass
        ]
        companion = sidecar_path(target)
        error = None
        try:
            sidecar = read_sidecar(companion)
        except (SidecarError, OSError) as exc:
            sidecar = None
            error = f"the existing sidecar could not be parsed: {exc}"
        folder = relative.rsplit("/", 1)[0] if "/" in relative else "."
        return {
            "version": __version__,
            "path": relative,
            "name": target.name,
            "stem": target.stem,
            "folder": folder,
            "folder_editable": folder != ".",
            "suffix": target.suffix.casefold(),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "meta": meta,
            "properties": properties,
            "mass": mass,
            "mass_invalid": bool(meta.fields) and not valid_mass,
            "part_number_mismatch": bool(meta.part_number)
            and meta.part_number.casefold() != target.stem.casefold(),
            "sidecar": sidecar,
            "sidecar_name": companion.name,
            "sidecar_exists": companion.is_file(),
            "sidecar_text": companion.read_text(encoding="utf-8") if companion.is_file() else "",
            "referrers": build_index(root, cache=references).referring(target.name),
            "renameable": target.suffix.casefold() in RENAMEABLE_EXTENSIONS,
            "rename_error": None,
            "rename_pending": None,
            "rename_draft": None,
            "renamed": _flag(request.args.get("renamed")),
            "form_token": app.config["FORM_TOKEN"],
            "saved": _flag(request.args.get("saved")),
            "error": error,
            "draft": None,
        }

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
