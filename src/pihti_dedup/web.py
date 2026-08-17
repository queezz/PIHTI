"""Flask application for local duplicate review, catalog, and guarded quarantine."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import secrets
import threading
from collections import OrderedDict
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import unquote

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for
from markupsafe import escape

from pihti_dedup import __version__, geometry_preview
from pihti_dedup.cleanup import (
    execute_cleanup,
    execute_consolidation,
    execute_member_cleanup,
    plan_consolidation,
    plan_member_cleanup,
    plan_merge_exact_cleanup,
    read_quarantine_manifests,
    restore_quarantine_manifest,
)
from pihti_dedup.foldernote import (
    FolderNoteError,
    note_excerpt,
    read_folder_note,
    strip_autogen_marker,
    write_folder_note,
)
from pihti_dedup.git_filename_history import (
    GitHistoryError,
    materialize_historical_blob,
    query_filename_history,
)
from pihti_dedup.git_history import PullRequestMerge, recent_pull_request_merges
from pihti_dedup.inventor_meta import INVENTOR_EXTENSIONS, DocumentMeta, Preview, read_preview
from pihti_dedup.inventor_meta import read_document as read_inventor_document
from pihti_dedup.inventory import (
    ExcludedPath,
    FileRecord,
    Inventory,
    classify,
    scan_workspace,
    sha256_file,
)
from pihti_dedup.markdown_view import render as render_markdown
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

# Durable repository knowledge: these complete top-level trees arrived as
# submissions. A merge may also touch an established tree such as
# ContentCenter; that does not turn the established tree into a PR folder.
KNOWN_PR_FOLDERS: dict[str, tuple[int, ...]] = {
    "BoronProbe_2026": (1, 3),
    "Plasma Vessel_2026": (1, 3),
    "bellows": (2,),
}


def _completed_cleanup(
    root: Path, group_id: str, *, path: str = "", keep_path: str = ""
) -> dict | None:
    """Return a prior matching quarantine event for an idempotent stale retry."""

    for event in read_quarantine_manifests(root):
        if event.get("restored_at"):
            continue
        if str(event.get("group_id", "")) != group_id:
            continue
        if keep_path and str(event.get("keep_path", "")).casefold() != keep_path.casefold():
            continue
        files = event.get("files", [])
        moved = [str(item.get("path", "")) for item in files if item.get("path")]
        if path and path.casefold() not in {item.casefold() for item in moved}:
            continue
        manifest = str(event["manifest"])
        return {
            "already_applied": True,
            "execution": {
                "group_id": group_id,
                "quarantine": str(Path(manifest).parent),
                "manifest": manifest,
                "moved": moved,
            },
        }
    return None


def _removed_batches(manifests: tuple[dict, ...], *, gap_seconds: int = 600) -> list[dict]:
    """Group adjacent cleanup events into compact, time-bounded sessions."""

    batches: list[dict] = []
    for event in manifests:
        source = str(event.get("source", "cleanup"))
        status = "restored" if event.get("restored_at") else "recoverable"
        try:
            created = datetime.fromisoformat(str(event.get("created_at", "")))
        except ValueError:
            created = None
        previous = batches[-1] if batches else None
        previous_created = previous["oldest_created"] if previous else None
        joins_previous = bool(
            previous
            and previous["source"] == source
            and previous["status"] == status
            and created is not None
            and previous_created is not None
            and abs((previous_created - created).total_seconds()) <= gap_seconds
        )
        if not joins_previous:
            previous = {
                "source": source,
                "status": status,
                "events": [],
                "newest": str(event.get("created_at", "")),
                "oldest": str(event.get("created_at", "")),
                "oldest_created": created,
                "files": 0,
            }
            batches.append(previous)
        previous["events"].append(event)
        previous["oldest"] = str(event.get("created_at", ""))
        previous["oldest_created"] = created
        previous["files"] += len(event.get("files", []))
    return batches


class InventoryCache:
    """Disk-aware inventory cache shared by every viewer surface.

    A ten-second time-to-live used to make normal tab switches hash the whole
    workspace again.  This cache instead performs a metadata-only validation,
    reuses hashes for files whose path, size, and modification time are
    unchanged, and persists that knowledge beneath the viewer's ignored cache
    directory so a server restart is not a cold start.
    """

    SCHEMA_VERSION = 1

    def __init__(self, workspace: Path, scanner: Scanner) -> None:
        self.workspace = workspace
        self.scanner = scanner
        self._lock = threading.Lock()
        self._entries: dict[bool, Inventory] = {}

    def _path(self, include_vendor: bool) -> Path:
        scope = "vendor" if include_vendor else "default"
        return self.workspace / ".pihti-dedup" / f"inventory-{scope}-v1.json"

    @staticmethod
    def _same_file(left: FileRecord, right: FileRecord) -> bool:
        return (
            left.path == right.path
            and left.size == right.size
            and left.mtime_ns == right.mtime_ns
        )

    @classmethod
    def _same_snapshot(cls, left: Inventory, right: Inventory) -> bool:
        return (
            len(left.records) == len(right.records)
            and all(cls._same_file(a, b) for a, b in zip(left.records, right.records))
            and left.excluded == right.excluded
            and left.errors == right.errors
        )

    @staticmethod
    def _inventory(snapshot: Inventory, records: list[FileRecord]) -> Inventory:
        filename_groups, renamed_groups = classify(records)
        return Inventory(
            root=snapshot.root,
            records=tuple(records),
            filename_groups=filename_groups,
            renamed_groups=renamed_groups,
            excluded=snapshot.excluded,
            errors=snapshot.errors,
            include_vendor=snapshot.include_vendor,
            extensions=snapshot.extensions,
            generated_at=snapshot.generated_at,
        )

    def _merge_hashes(
        self,
        snapshot: Inventory,
        previous: Inventory | None,
        *,
        hash_files: bool,
        force: bool,
    ) -> Inventory:
        old = {record.path: record for record in previous.records} if previous else {}
        records: list[FileRecord] = []
        for record in snapshot.records:
            prior = old.get(record.path)
            digest = None
            if not force and prior and self._same_file(record, prior):
                digest = prior.sha256
            if hash_files and digest is None:
                try:
                    digest = sha256_file(self.workspace / record.path)
                except OSError as exc:
                    errors = (*snapshot.errors, f"cannot hash {record.path}: {exc}")
                    snapshot = replace(snapshot, errors=errors)
            records.append(replace(record, sha256=digest))
        return self._inventory(snapshot, records)

    def _load(self, include_vendor: bool) -> Inventory | None:
        try:
            payload = json.loads(self._path(include_vendor).read_text(encoding="utf-8"))
            if (
                payload.get("schema_version") != self.SCHEMA_VERSION
                or payload.get("include_vendor") != include_vendor
            ):
                return None
            records = [FileRecord(**item) for item in payload["records"]]
            snapshot = Inventory(
                root=self.workspace,
                records=(),
                filename_groups=(),
                renamed_groups=(),
                excluded=tuple(ExcludedPath(**item) for item in payload.get("excluded", [])),
                errors=tuple(payload.get("errors", [])),
                include_vendor=include_vendor,
                extensions=tuple(payload["extensions"]) if payload.get("extensions") else None,
                generated_at=str(payload["generated_at"]),
            )
            return self._inventory(snapshot, records)
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _store(self, inventory: Inventory) -> None:
        target = self._path(inventory.include_vendor)
        temporary = target.with_suffix(".tmp")
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "include_vendor": inventory.include_vendor,
            "generated_at": inventory.generated_at,
            "extensions": list(inventory.extensions) if inventory.extensions else None,
            "records": [asdict(record) for record in inventory.records],
            "excluded": [asdict(item) for item in inventory.excluded],
            "errors": list(inventory.errors),
        }
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            temporary.replace(target)
        except OSError:
            # This is a performance cache. A read-only workspace must still be
            # fully usable; it simply pays for hashing again after a restart.
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def get(
        self, *, include_vendor: bool, hash_files: bool = True, force: bool = False
    ) -> Inventory:
        with self._lock:
            previous = self._entries.get(include_vendor)
            if previous is None:
                previous = self._load(include_vendor)
            if previous is None:
                # The vendor scope is a superset of the default scope. Reuse
                # every overlapping digest when the owner toggles that view
                # instead of hashing the same thousand files a second time.
                previous = self._entries.get(not include_vendor) or self._load(
                    not include_vendor
                )
            snapshot = self.scanner(
                self.workspace, include_vendor=include_vendor, hash_files=False
            )
            if previous is not None and not force and self._same_snapshot(snapshot, previous):
                if not hash_files or all(record.sha256 for record in previous.records):
                    self._entries[include_vendor] = previous
                    return previous
            inventory = self._merge_hashes(
                snapshot, previous, hash_files=hash_files, force=force
            )
            self._entries[include_vendor] = inventory
            self._store(inventory)
            return inventory

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class PreviewCache:
    """Previews keyed by path and modification time.

    Two sources sit behind one cache. An Inventor document already carries a
    thumbnail, and lifting it out costs a few milliseconds. An `.stl`, `.step`,
    `.3mf`, or `.dwg` does not, so `geometry_preview` draws one — and that costs
    seconds for STEP, which is why it has a disk cache of its own underneath
    this one.

    A catalog page asks for hundreds of previews at once and re-asks on every
    visit, so misses are memoized too: a `.dxf`, or a STEP file with the `step`
    extra absent, stays cheap instead of being re-attempted per request. The
    memo is per process; `geometry_preview` deliberately caches successes only.
    """

    def __init__(self, workspace: Path, limit: int = 512) -> None:
        self.workspace = workspace
        self.limit = limit
        self._lock = threading.Lock()
        self._entries: OrderedDict[tuple[str, int], Preview | None] = OrderedDict()

    def get(self, path: Path, mtime_ns: int, st_size: int | None = None) -> Preview | None:
        key = (os.path.normcase(str(path)), mtime_ns)
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key]
        preview = self._read(path, mtime_ns, st_size)
        with self._lock:
            self._entries[key] = preview
            self._entries.move_to_end(key)
            while len(self._entries) > self.limit:
                self._entries.popitem(last=False)
        return preview

    def _read(self, path: Path, mtime_ns: int, st_size: int | None) -> Preview | None:
        suffix = path.suffix.casefold()
        if suffix in INVENTOR_EXTENSIONS:
            return read_preview(path)
        if suffix in geometry_preview.available_extensions():
            return geometry_preview.get_or_render(
                self.workspace, path, mtime_ns, st_size=st_size
            )
        return None


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


def _preview_etag(path: Path, stat: os.stat_result, preview: Preview | None) -> str:
    """A validator covering everything that can change the served bytes.

    The URL stays the same when a CAD file is resaved, so the validator has to
    carry the identity instead: path, modification time, size, the renderer
    version that would draw it, and whether this response is a real preview or
    the placeholder — installing the `step` extra turns the latter into the
    former without touching the file.
    """

    raw = "\0".join(
        [
            os.path.normcase(str(path)),
            str(stat.st_mtime_ns),
            str(stat.st_size),
            str(geometry_preview.RENDERER_VERSION),
            preview.image_format if preview else "placeholder",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


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


def _note_display_text(note) -> str:
    """Text to show in the folder-note textarea.

    An autogenerated README still carries the generator's leading HTML comment
    block ("Editing this file ... claims it as your folder note"), which reads
    as a warning rather than the invitation the editor makes. `write_folder_note`
    already strips that same block on save, so the file the owner reads back is
    never confused with what they typed; reuse that stripping here for display
    too instead of showing the raw comment first.
    """

    if note is None:
        return ""
    return strip_autogen_marker(note.text) if note.generated else note.text


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


GENERIC_CAD_STEM = re.compile(
    r"^(?:body|part|component|solid|surface|assembly|group|base|imported|model)[ _-]*\d*$",
    re.IGNORECASE,
)


def _is_generic_cad_name(value: str) -> bool:
    """Flag low-information names commonly emitted by imported geometry."""

    return bool(GENERIC_CAD_STEM.fullmatch(Path(value).stem.strip()))


def _display_reference_name(value: str) -> str:
    """Decode Inventor's duplicate URL-encoded filename strings for display."""

    try:
        decoded = unquote(value, errors="strict")
    except UnicodeDecodeError:
        return value
    if not decoded or "/" in decoded or "\\" in decoded:
        return value
    return decoded


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


def folder_tree(folders: list[dict], current: str = ".") -> list[dict]:
    """Nest the catalog folder index and open only the current branch.

    A flat rail of 99 folders buries the scan card and cannot be skimmed, and
    the owner rejected an inner scrollbar as the fix. A tree shows the handful
    of top-level systems, each carrying the file count of its whole subtree, and
    opens only where asked.
    """

    roots: dict[str, dict] = {}
    for folder in folders:
        if folder["name"] == ".":
            continue
        parts = folder["name"].split("/")
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
                    "current": False,
                    "open": False,
                    "children": {},
                },
            )
            store = node["children"]
        if node is not None:
            node["count"] = folder["count"]
            node["current"] = folder["name"] == current
            node["open"] = current == folder["name"] or current.startswith(
                f"{folder['name']}/"
            )
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
    previews = PreviewCache(root)
    references = ReferenceCache()
    catalog_metadata: dict[str, tuple[int, int, DocumentMeta]] = {}
    catalog_metadata_lock = threading.RLock()
    app.extensions["pihti_inventory_cache"] = cache
    app.extensions["pihti_preview_cache"] = previews
    app.extensions["pihti_reference_cache"] = references
    app.jinja_env.filters["filesize"] = _filesize
    app.jinja_env.filters["winpath"] = _windows_path
    app.jinja_env.filters["filetime"] = _filetime
    app.jinja_env.tests["newver_name"] = _is_newver_name
    app.jinja_env.tests["generic_cad_name"] = _is_generic_cad_name
    app.jinja_env.globals["RENAMEABLE_EXTENSIONS"] = RENAMEABLE_EXTENSIONS

    @app.context_processor
    def global_recovery_status():
        recoverable = [
            event for event in read_quarantine_manifests(root) if not event.get("restored_at")
        ]
        return {
            "recoverable_events": len(recoverable),
            "recoverable_files": sum(len(event.get("files", ())) for event in recoverable),
        }

    @app.after_request
    def no_store(response):
        # `/preview/...` is exempt. Every other page reports live filesystem
        # state that a cached copy would misreport, but a preview is keyed by
        # the file's own modification time and carries an ETag and
        # Last-Modified, so a conditional request is exact rather than
        # optimistic. A rendered STEP costs seconds; making the browser refetch
        # 280 of them on every catalog visit would defeat the disk cache.
        if request.endpoint in {"preview_image", "git_history_preview"}:
            return response
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/duplicates")
    def duplicates():
        return render_template("duplicates.html", workspace=root.name, version=__version__)

    @app.get("/doctor")
    def doctor():
        inventory = cache.get(include_vendor=False)
        index = build_index(root, cache=references)
        locations = filename_locations(root)
        generic: dict[str, list[FileRecord]] = {}
        for record in inventory.records:
            if (
                record.suffix.casefold() in RENAMEABLE_EXTENSIONS
                and _is_generic_cad_name(record.name)
            ):
                generic.setdefault(record.name_key, []).append(record)
        generic_views = [
            {
                "name": records[0].name,
                "records": tuple(sorted(records, key=lambda item: item.path.casefold())),
                "referrers": index.referring(records[0].name),
            }
            for records in generic.values()
        ]
        generic_views.sort(
            key=lambda item: (-len(item["records"]), item["name"].casefold())
        )
        assembly_views = []
        for path, names in index.document_names.items():
            if Path(path).suffix.casefold() != ".iam":
                continue
            distinct_names = {
                _display_reference_name(name).casefold(): _display_reference_name(name)
                for name in names
            }
            problems = [
                name
                for name in distinct_names.values()
                if _is_generic_cad_name(name)
                or len(locations.get(name.casefold(), ())) != 1
            ]
            if not problems:
                continue
            assembly_views.append(
                {
                    "path": path,
                    "name": Path(path).name,
                    "problem_count": len(problems),
                    "generic_count": sum(_is_generic_cad_name(name) for name in problems),
                    "missing_count": sum(
                        not locations.get(name.casefold(), ()) for name in problems
                    ),
                    "ambiguous_count": sum(
                        len(locations.get(name.casefold(), ())) > 1 for name in problems
                    ),
                }
            )
        assembly_views.sort(
            key=lambda item: (
                -item["missing_count"],
                -item["problem_count"],
                item["path"].casefold(),
            )
        )
        return render_template(
            "doctor.html",
            version=__version__,
            workspace=root.name,
            collisions=tuple(
                group
                for group in inventory.filename_groups
                if group.records
                and all(
                    record.suffix.casefold() in RENAMEABLE_EXTENSIONS
                    for record in group.records
                )
            ),
            generic_names=generic_views,
            assemblies=[item for item in assembly_views if item["generic_count"]],
            missing_assemblies=[
                item for item in assembly_views if not item["generic_count"]
            ],
        )

    def _validated_doctor_assembly(value: str) -> str:
        target = workspace_file(root, value)
        if target is None or target.suffix.casefold() != ".iam":
            return ""
        return target.relative_to(root).as_posix()

    @app.get("/doctor/assembly/<path:relative_path>")
    def doctor_assembly(relative_path: str):
        assembly_path = _validated_doctor_assembly(relative_path)
        if not assembly_path:
            return render_template(
                "_not_found.html", version=__version__, path=relative_path
            ), 404
        target = root / assembly_path
        index = build_index(root, cache=references)
        locations = filename_locations(root)
        ledger = read_ledger(root)
        problems = []
        reference_groups: dict[str, list[str]] = {}
        for raw_name in index.names_in(assembly_path):
            display_name = _display_reference_name(raw_name)
            reference_groups.setdefault(display_name.casefold(), []).append(raw_name)
        for aliases in reference_groups.values():
            name = _display_reference_name(aliases[0])
            paths = locations.get(name.casefold(), ())
            generic = _is_generic_cad_name(name)
            if not generic and len(paths) == 1:
                continue
            candidates = [
                {
                    "path": path,
                    "absolute": str(root / path),
                    "folder_absolute": str((root / path).parent),
                    "same_folder": Path(path).parent == Path(assembly_path).parent,
                }
                for path in paths
            ]
            candidates.sort(
                key=lambda item: (not item["same_folder"], item["path"].casefold())
            )
            history = None
            history_error = ""
            if not paths:
                try:
                    result = query_filename_history(root, name)
                    history = {
                        "found": result.found,
                        "occurrences": [
                            {
                                "commit": occurrence.commit,
                                "committed_at": occurrence.committed_at,
                                "subject": occurrence.subject,
                                "status": occurrence.status,
                                "path": occurrence.path,
                                "rename_destination": occurrence.rename_destination,
                                "preview_path": occurrence.rename_destination
                                if occurrence.status[:1] in {"R", "C"}
                                and occurrence.rename_destination
                                else occurrence.path,
                                "current_destination": (
                                    occurrence.rename_destination
                                    if occurrence.rename_destination
                                    and workspace_file(root, occurrence.rename_destination)
                                    else ""
                                ),
                                "current_destination_absolute": (
                                    str(root / occurrence.rename_destination)
                                    if occurrence.rename_destination
                                    and workspace_file(root, occurrence.rename_destination)
                                    else ""
                                ),
                            }
                            for occurrence in result.occurrences
                        ],
                    }
                except (GitHistoryError, OSError, ValueError) as exc:
                    history_error = str(exc)
            problems.append(
                {
                    "name": name,
                    "aliases": tuple(
                        alias for alias in aliases if alias.casefold() != name.casefold()
                    ),
                    "generic": generic,
                    "candidates": candidates,
                    "renamed": tuple(
                        reversed(
                            [
                                entry
                                for entry in ledger
                                if entry.old_name.casefold() == name.casefold()
                            ]
                        )
                    ),
                    "status": "missing" if not paths else "ambiguous" if len(paths) > 1 else "generic",
                    "history": history,
                    "history_error": history_error,
                }
            )
        status_order = {"missing": 0, "ambiguous": 1, "generic": 2}
        problems.sort(
            key=lambda item: (status_order[item["status"]], item["name"].casefold())
        )
        return render_template(
            "doctor_assembly.html",
            version=__version__,
            workspace=root.name,
            assembly={
                "path": assembly_path,
                "name": target.name,
                "absolute": str(target),
                "folder_absolute": str(target.parent),
            },
            problems=problems,
            renamed=_flag(request.args.get("renamed")),
        )

    @app.get("/doctor/history-preview/<commit>/<path:relative_path>")
    def git_history_preview(commit: str, relative_path: str):
        try:
            data = materialize_historical_blob(root, commit, relative_path)
        except (GitHistoryError, OSError, ValueError):
            return Response("historical file unavailable", status=404, mimetype="text/plain")
        digest = hashlib.sha256(
            f"{commit}:{relative_path}".encode("utf-8", "surrogatepass")
        ).hexdigest()
        store = root / ".pihti-dedup" / "git-previews"
        cached = store / f"{digest}{Path(relative_path).suffix.lower()}"
        try:
            store.mkdir(parents=True, exist_ok=True)
            if not cached.is_file() or cached.stat().st_size != len(data):
                temporary = cached.with_suffix(cached.suffix + ".tmp")
                temporary.write_bytes(data)
                temporary.replace(cached)
            preview = read_preview(cached)
        except OSError:
            preview = None
        if preview is None:
            response = Response(
                placeholder_svg(Path(relative_path).suffix), mimetype="image/svg+xml"
            )
        else:
            response = Response(preview.data, mimetype=preview.media_type)
        response.set_etag(digest)
        response.cache_control.private = True
        response.cache_control.no_cache = True
        return response.make_conditional(request)

    def _doctor_name_context(
        filename: str,
        *,
        error: str | None = None,
        draft_path: str = "",
        draft_name: str = "",
        pending=None,
    ) -> dict:
        locations = filename_locations(root)
        current_paths = locations.get(filename.casefold(), ())
        current_members = [
            {
                "path": path,
                "stem": Path(path).stem,
                "suffix": Path(path).suffix,
                "absolute": str(root / path),
                "folder_absolute": str((root / path).parent),
            }
            for path in current_paths
        ]
        entries = tuple(
            reversed(
                [
                    entry
                    for entry in read_ledger(root)
                    if entry.old_name.casefold() == filename.casefold()
                ]
            )
        )
        index = build_index(root, cache=references)
        assembly_path = _validated_doctor_assembly(request.values.get("assembly", ""))
        return {
            "version": __version__,
            "workspace": root.name,
            "filename": filename,
            "current_paths": current_paths,
            "current_members": current_members,
            "entries": entries,
            "referrers": [
                {
                    "path": path,
                    "absolute": str(root / path),
                    "folder_absolute": str((root / path).parent),
                }
                for path in index.referring(filename)
            ],
            "current_will_prompt": not current_paths,
            "generic_name": _is_generic_cad_name(filename),
            "form_token": app.config["FORM_TOKEN"],
            "rename_error": error,
            "draft_path": draft_path,
            "draft_name": draft_name,
            "rename_pending": pending,
            "renamed": _flag(request.args.get("renamed")),
            "root": root,
            "assembly_path": assembly_path,
            "doctor_name_action": url_for(
                "doctor_name", filename=filename, assembly=assembly_path or None
            ),
        }

    @app.route("/doctor/name/<filename>", methods=["GET", "POST"])
    def doctor_name(filename: str):
        if request.method == "GET":
            return render_template("doctor_name.html", **_doctor_name_context(filename))
        guard = _guard(request)
        if guard is not None:
            return guard
        relative_path = request.form.get("relative_path", "")
        new_name = request.form.get("new_name", "")
        target = workspace_file(root, relative_path)
        if target is None or target.name.casefold() != filename.casefold():
            return render_template(
                "doctor_name.html",
                **_doctor_name_context(
                    filename,
                    error="that member is no longer part of this name repair session",
                    draft_path=relative_path,
                    draft_name=new_name,
                ),
            ), 409
        confirmed = _flag(request.form.get("confirm_collision"))
        index = build_index(root, cache=references)
        try:
            plan = plan_rename(
                root,
                relative_path,
                new_name,
                index=index,
                locations=filename_locations(root),
            )
        except RenameError as exc:
            return render_template(
                "doctor_name.html",
                **_doctor_name_context(
                    filename,
                    error=str(exc),
                    draft_path=relative_path,
                    draft_name=new_name,
                ),
            ), 400
        if plan.needs_confirmation and not confirmed:
            return render_template(
                "doctor_name.html",
                **_doctor_name_context(
                    filename,
                    draft_path=relative_path,
                    draft_name=plan.new_name,
                    pending=plan,
                ),
            ), 409
        try:
            execute_rename(root, plan, confirmed=confirmed)
        except (RenameError, OSError) as exc:
            return render_template(
                "doctor_name.html",
                **_doctor_name_context(
                    filename,
                    error=str(exc),
                    draft_path=relative_path,
                    draft_name=new_name,
                ),
            ), 409
        cache.clear()
        assembly_path = _validated_doctor_assembly(request.values.get("assembly", ""))
        if assembly_path:
            return redirect(
                url_for("doctor_assembly", relative_path=assembly_path, renamed="1")
            )
        return redirect(url_for("doctor_name", filename=filename, renamed="1"))

    @app.get("/")
    def index():
        return redirect(url_for("catalog"))

    @app.post("/markdown/preview")
    def markdown_preview():
        """Render unsaved local-note Markdown without writing workspace data."""
        return jsonify(html=render_markdown(request.form.get("text", "")))

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
        pr_folders: dict[str, list[int]] = {
            folder.casefold(): list(numbers) for folder, numbers in KNOWN_PR_FOLDERS.items()
        }
        merges = tuple(merge_reader(root))
        group_merges: dict[str, list[str]] = {group.id: [] for group in inventory.groups}
        for merge in merges:
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
        record_prs = {}
        for record in inventory.records:
            folder_prs = pr_folders.get(record.path.split("/", 1)[0].casefold(), [])
            added_prs = [merge.number for merge in merges if record.path in merge.added_paths]
            edited_prs = [
                merge.number
                for merge in merges
                if record.path in merge.paths and record.path not in merge.added_paths
            ]
            record_prs[record.path] = {
                "folder": folder_prs,
                "added": added_prs,
                "edited": edited_prs,
                "target": bool(folder_prs or added_prs),
            }
        extensions = sorted({suffix for group in inventory.groups for suffix in group.extensions})
        member_plans = {}
        for group in inventory.groups:
            if group.kind not in {"exact", "renamed", "collision"}:
                continue
            for record in group.records:
                try:
                    plan = plan_member_cleanup(
                        inventory,
                        group_id=group.id,
                        path=record.path,
                        allow_collision=group.kind == "collision",
                    )
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
            record_prs=record_prs,
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
        inventory = cache.get(include_vendor=include_vendor)
        plan = plan_merge_exact_cleanup(inventory, merge)
        if not secrets.compare_digest(str(payload.get("signature", "")), plan.signature):
            return jsonify({"error": "cleanup plan changed; run the dry preview again"}), 409
        try:
            execution = execute_cleanup(root, plan, references_checked=True)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify({"execution": execution.to_dict(), "rescan_pending": True})

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
        inventory = cache.get(include_vendor=include_vendor)
        try:
            plan = plan_member_cleanup(
                inventory, group_id=group_id, path=path, allow_collision=True
            )
        except ValueError as exc:
            completed = _completed_cleanup(root, group_id, path=path)
            if completed is not None:
                completed["post_scan"] = inventory.summary
                return jsonify(completed)
            return jsonify({"error": str(exc)}), 409
        if plan.group_kind == "collision" and payload.get("reviewed") is not True:
            return jsonify({"error": "the selected revision must be reviewed first"}), 400
        if not secrets.compare_digest(str(payload.get("signature", "")), plan.signature):
            return jsonify({"error": "cleanup member changed; rescan and try again"}), 409
        try:
            index = build_index(root, cache=references)
            execution = execute_member_cleanup(
                root,
                plan,
                references_checked=True,
                where_used=index.referring(plan.candidate.name),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify({"execution": execution.to_dict(), "rescan_pending": True})

    @app.post("/duplicates/member/<group_id>/consolidate")
    def consolidation_apply(group_id: str):
        if not _is_loopback(request.remote_addr):
            return jsonify({"error": "cleanup is restricted to localhost"}), 403
        if not secrets.compare_digest(
            request.headers.get("X-PIHTI-Token", ""), app.config["FORM_TOKEN"]
        ):
            return jsonify({"error": "invalid form token"}), 403
        payload = request.get_json(silent=True) or {}
        if payload.get("reviewed") is not True:
            return jsonify({"error": "the revisions must be opened and compared first"}), 400
        include_vendor = bool(payload.get("include_vendor"))
        inventory = cache.get(include_vendor=include_vendor)
        keep_path = str(payload.get("keep_path", ""))
        try:
            plan = plan_consolidation(
                inventory, group_id=group_id, keep_path=keep_path
            )
            index = build_index(root, cache=references)
            execution = execute_consolidation(
                root,
                plan,
                references_checked=True,
                where_used=index.referring(plan.candidates[0].name),
            )
        except (OSError, ValueError) as exc:
            completed = _completed_cleanup(root, group_id, keep_path=keep_path)
            if completed is not None:
                completed["post_scan"] = inventory.summary
                return jsonify(completed)
            return jsonify({"error": str(exc)}), 409
        return jsonify({"execution": execution.to_dict(), "rescan_pending": True})

    @app.get("/removed")
    def removed():
        query = request.args.get("q", "").strip()
        manifests = read_quarantine_manifests(root)
        if query:
            needle = query.casefold()
            manifests = tuple(
                event
                for event in manifests
                if needle in json.dumps(event, ensure_ascii=False).casefold()
            )
        summary = {
            "events": len(manifests),
            "recoverable": sum(not event.get("restored_at") for event in manifests),
            "restored": sum(bool(event.get("restored_at")) for event in manifests),
            "files": sum(len(event.get("files", [])) for event in manifests),
        }
        return render_template(
            "removed.html",
            version=__version__,
            workspace=root.name,
            manifests=manifests,
            batches=_removed_batches(manifests),
            summary=summary,
            query=query,
            form_token=app.config["FORM_TOKEN"],
            restored=_flag(request.args.get("restored")),
        )

    @app.post("/removed/restore")
    def removed_restore():
        guard = _guard(request)
        if guard is not None:
            return guard
        try:
            restore_quarantine_manifest(root, request.form.get("manifest", ""))
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
            return Response(str(exc), status=409, mimetype="text/plain")
        cache.clear()
        return redirect(url_for("removed", restored="1"))

    @app.get("/preview/<path:relative_path>")
    def preview_image(relative_path: str):
        target = workspace_file(root, relative_path)
        if target is None:
            return Response("no such workspace file", status=404, mimetype="text/plain")
        try:
            stat = target.stat()
        except OSError:
            return Response("no such workspace file", status=404, mimetype="text/plain")
        preview = previews.get(target, stat.st_mtime_ns, stat.st_size)
        if preview is None:
            response = Response(placeholder_svg(target.suffix), mimetype="image/svg+xml")
        else:
            response = Response(preview.data, mimetype=preview.media_type)
        response.last_modified = stat.st_mtime
        response.set_etag(_preview_etag(target, stat, preview))
        response.cache_control.private = True
        response.cache_control.no_cache = True  # revalidate, never serve stale
        return response.make_conditional(request)

    @app.get("/catalog", defaults={"relative_folder": None})
    @app.get("/catalog/<path:relative_folder>")
    def catalog(relative_folder: str | None):
        include_vendor = _flag(request.args.get("include_vendor"))
        inventory = cache.get(include_vendor=include_vendor, hash_files=False)
        current = "."
        if relative_folder is not None:
            target = workspace_folder(root, relative_folder)
            if target is None:
                return render_template(
                    "_not_found.html", version=__version__, path=relative_folder
                ), 404
            current = target.relative_to(root).as_posix()
        return render_template("catalog.html", **_catalog_context(inventory, current))

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
            if request.form.get("origin") == "catalog":
                return _catalog_note_error(target, text, str(exc), 400)
            context = _folder_context(target)
            context.update(error=str(exc), draft=text)
            return render_template("folder.html", **context), 400
        except OSError as exc:
            if request.form.get("origin") == "catalog":
                return _catalog_note_error(
                    target, text, f"could not write the folder note: {exc}", 500
                )
            context = _folder_context(target)
            context.update(error=f"could not write the folder note: {exc}", draft=text)
            return render_template("folder.html", **context), 500
        relative = target.relative_to(root).as_posix()
        if request.form.get("origin") == "catalog":
            return redirect(
                url_for(
                    "catalog",
                    relative_folder=relative,
                    saved="1",
                    include_vendor=(
                        "1" if _flag(request.form.get("include_vendor")) else None
                    ),
                )
            )
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
        locations = filename_locations(root)
        views = [_rename_view(entry, locations) for entry in entries]
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

    def _catalog_index(inventory: Inventory) -> list[dict]:
        stats: dict[str, dict] = {
            ".": {"name": ".", "count": 0, "direct_count": 0, "children": set()}
        }
        for record in inventory.records:
            parent = record.path.rsplit("/", 1)[0] if "/" in record.path else "."
            stats["."]["count"] += 1
            if parent == ".":
                stats["."]["direct_count"] += 1
                continue
            ancestor = "."
            walked: list[str] = []
            for part in parent.split("/"):
                walked.append(part)
                path = "/".join(walked)
                stats.setdefault(
                    path,
                    {"name": path, "count": 0, "direct_count": 0, "children": set()},
                )
                stats[path]["count"] += 1
                stats[ancestor]["children"].add(path)
                ancestor = path
            stats[parent]["direct_count"] += 1
        return [
            {
                "name": item["name"],
                "count": item["count"],
                "direct_count": item["direct_count"],
                "child_count": len(item["children"]),
                "children": tuple(sorted(item["children"], key=str.casefold)),
            }
            for item in sorted(stats.values(), key=lambda value: value["name"].casefold())
        ]

    def _read_catalog_note(path: str):
        if path == ".":
            return None
        try:
            return read_folder_note(root / path)
        except (FolderNoteError, OSError):
            return None

    def _workspace_summary() -> str:
        try:
            note = read_folder_note(root)
        except (FolderNoteError, OSError):
            return ""
        return note.excerpt if note else ""

    def _folder_card(item: dict) -> dict:
        note = _read_catalog_note(item["name"])
        return {
            **item,
            "label": item["name"].rsplit("/", 1)[-1],
            "excerpt": note.excerpt if note and not note.generated else "",
        }

    def _catalog_document_meta(record: FileRecord) -> DocumentMeta | None:
        if record.suffix.casefold() not in INVENTOR_EXTENSIONS:
            return None
        with catalog_metadata_lock:
            cached = catalog_metadata.get(record.path)
            if cached and cached[:2] == (record.mtime_ns, record.size):
                return cached[2]
        target = root / record.path
        try:
            meta = read_inventor_document(target)
        except OSError as exc:
            meta = DocumentMeta(path=str(target), ok=False, error=str(exc))
        with catalog_metadata_lock:
            catalog_metadata[record.path] = (record.mtime_ns, record.size, meta)
        return meta

    def _catalog_file(record: FileRecord) -> dict:
        target = root / record.path
        companion = sidecar_path(target)
        metadata_error = ""
        try:
            sidecar = read_sidecar(companion)
        except (SidecarError, OSError, UnicodeDecodeError):
            sidecar = None
            metadata_error = "Metadata sidecar needs repair."

        meta = _catalog_document_meta(record)
        fields = meta.fields if meta else {}
        description = str(fields.get("description") or "").strip()
        summary = note_excerpt(sidecar.body, limit=180) if sidecar else ""
        summary = summary or description
        status = sidecar.status if sidecar else ""
        tags = sidecar.tags[:3] if sidecar else ()
        material = str(
            (sidecar.frontmatter.get("material") if sidecar else "")
            or fields.get("material")
            or ""
        ).strip()
        if material.casefold() in {"generic", "default"}:
            material = ""
        part_number = str(
            (sidecar.frontmatter.get("part_number") if sidecar else "")
            or fields.get("part_number")
            or ""
        ).strip()
        if part_number.casefold() == Path(record.name).stem.casefold():
            part_number = ""
        has_metadata = bool(
            summary or status or tags or material or part_number or metadata_error
        )
        has_story = bool(summary or metadata_error)
        return {
            "record": record,
            "summary": summary or metadata_error,
            "status": status,
            "tags": tags,
            "material": material,
            "part_number": part_number,
            "has_metadata": has_metadata,
            "has_story": has_story,
            "sidecar": sidecar is not None,
        }

    def _breadcrumbs(path: str) -> list[dict]:
        crumbs = [{"name": "Catalog", "path": "."}]
        if path == ".":
            return crumbs
        walked: list[str] = []
        for part in path.split("/"):
            walked.append(part)
            crumbs.append({"name": part, "path": "/".join(walked)})
        return crumbs

    def _catalog_context(inventory: Inventory, current: str) -> dict:
        index = _catalog_index(inventory)
        by_name = {item["name"]: item for item in index}
        current_stats = by_name.get(
            current,
            {"name": current, "count": 0, "direct_count": 0, "children": ()},
        )
        query = request.args.get("q", "").strip()
        try:
            requested = int(request.args.get("show", "48"))
        except ValueError:
            requested = 48
        show = max(48, min(requested, len(inventory.records) or 48))

        if query:
            folded = query.casefold()
            matching = [record for record in inventory.records if folded in record.path.casefold()]
            child_folders: list[dict] = []
            records = matching[:show]
            total = len(matching)
        else:
            child_folders = [_folder_card(by_name[name]) for name in current_stats["children"]]
            records = [
                record
                for record in inventory.records
                if (record.path.rsplit("/", 1)[0] if "/" in record.path else ".") == current
            ][:show]
            total = current_stats["direct_count"]

        files = [_catalog_file(record) for record in records]

        note = _read_catalog_note(current)
        note_text = _note_display_text(note)
        return {
            "version": __version__,
            "inventory": inventory,
            "file_count": len(inventory.records),
            "folder_count": max(0, len(index) - 1),
            "path": current,
            "name": "Catalog" if current == "." else current.rsplit("/", 1)[-1],
            "breadcrumbs": _breadcrumbs(current),
            "child_folders": child_folders,
            "files": files,
            "shown": len(files),
            "result_total": total,
            "query": query,
            "next_show": min(total, show + 48),
            "has_more": len(files) < total,
            "subtree_count": current_stats["count"],
            "direct_count": current_stats["direct_count"],
            "tree": folder_tree(index, current=current),
            "note": note,
            "workspace_summary": _workspace_summary() if current == "." else "",
            "note_text": note_text,
            "note_html": render_markdown(note_text),
            "note_error": None,
            "note_draft": None,
            "note_dialog_open": _flag(request.args.get("saved")),
            "saved": _flag(request.args.get("saved")),
            "form_token": app.config["FORM_TOKEN"],
            "include_vendor": inventory.include_vendor,
        }

    def _catalog_note_error(target: Path, draft: str, error: str, status: int):
        relative = target.relative_to(root).as_posix()
        include_vendor = _flag(request.form.get("include_vendor"))
        inventory = cache.get(include_vendor=include_vendor, hash_files=False)
        context = _catalog_context(inventory, relative)
        context.update(
            note_error=error,
            note_draft=draft,
            note_dialog_open=True,
        )
        return render_template("catalog.html", **context), status

    def _folder_context(target: Path) -> dict:
        relative = target.relative_to(root).as_posix()
        inventory = cache.get(include_vendor=True, hash_files=False)
        prefix = f"{relative}/"
        files = [
            _catalog_file(record)
            for record in inventory.records
            if record.path.rsplit("/", 1)[0] == relative
        ]
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
            "breadcrumbs": _breadcrumbs(relative),
            "files": files,
            "subtree_count": len(subtree),
            "note": note,
            "note_text": _note_display_text(note),
            "note_html": render_markdown(_note_display_text(note)),
            "form_token": app.config["FORM_TOKEN"],
            "saved": _flag(request.args.get("saved")),
            "error": error,
            "draft": None,
        }

    def _rename_view(entry, locations: dict[str, tuple[str, ...]]) -> dict:
        current_matches = locations.get(entry.old_name.casefold(), ())
        current_will_prompt = not current_matches
        return {
            "entry": entry,
            "full_path": str(root / entry.new_path),
            "folder_path": str((root / entry.new_path).parent),
            "search": f"{entry.old_name} {entry.new_name} {entry.new_path}".casefold(),
            "current_matches": current_matches,
            "current_will_prompt": current_will_prompt,
            "status_changed": current_will_prompt != entry.will_prompt,
        }

    @app.get("/part/<path:relative_path>")
    def part_page(relative_path: str):
        target = workspace_file(root, relative_path)
        if target is None:
            wanted = relative_path.replace("\\", "/").casefold()
            for event in read_quarantine_manifests(root):
                for item in event.get("files", []):
                    if str(item.get("path", "")).casefold() == wanted:
                        return render_template(
                            "removed_path.html",
                            version=__version__,
                            path=relative_path,
                            event=event,
                            item=item,
                        ), 410
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
            "preview_source": geometry_preview.preview_source(target.suffix),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "meta": meta,
            "properties": properties,
            "mass": mass,
            "mass_invalid": bool(meta.fields) and not valid_mass,
            "part_number_mismatch": bool(meta.part_number)
            and meta.part_number.casefold() != target.stem.casefold(),
            "sidecar": sidecar,
            "sidecar_html": render_markdown(sidecar.body if sidecar else ""),
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
