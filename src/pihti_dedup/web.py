"""Flask application for local duplicate review, catalog, and guarded quarantine."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import os
import re
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import unquote

from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, url_for
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
    authored_part,
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
from pihti_dedup.inventor_meta import (
    INVENTOR_EXTENSIONS,
    DocumentMeta,
    Preview,
    mass_properties,
    read_preview,
)
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
from pihti_dedup.sidecar import (
    FEATURED_KEY,
    HERO_KEY,
    SidecarError,
    read_sidecar,
    seed_text,
    set_flag,
    sidecar_path,
    write_sidecar,
)
from pihti_dedup.snapshots import Snapshot, Ticker, is_due
from pihti_dedup.sourcing import (
    ATTACHMENT_TYPES,
    IMAGE_EXTENSIONS,
    MAX_ATTACHMENT_BYTES,
    STATUS_VALUES,
    SourcingError,
    attachment_target,
    attachments_dir,
    is_slug,
    is_sourcing_path,
    note_path,
    parse_option,
    read_folder_options,
    rewrite_obsidian_embeds,
    save_attachment,
    sourcing_dir,
    status_counts,
    summary_line,
    unique_slug,
    write_option,
)
from pihti_dedup.standard_parts import (
    CONFLICT,
    DEFAULT_DESTINATION,
    IDENTICAL,
    MOVE,
    OUTCOMES,
    REFUSED,
    StandardMoveError,
    execute_standard_move,
    find_standard_candidates,
    is_standard_candidate,
    plan_standard_move,
)
from pihti_dedup.whereused import ReferenceCache, build_index, filename_locations

Scanner = Callable[..., Inventory]
MergeReader = Callable[[Path], tuple[PullRequestMerge, ...]]

logger = logging.getLogger(__name__)

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

    def __init__(
        self,
        workspace: Path,
        scanner: Scanner,
        *,
        max_age: float = 0.0,
        idle_interval: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        on_clear: Callable[[], None] | None = None,
    ) -> None:
        """`max_age == 0` validates the disk on every `get()`.

        `max_age > 0` serves the in-memory snapshot and leaves validation to
        `refresh()`/`refresh_due()` (a background ticker), except after
        `clear()`, on `force=True`/`fresh=True`, and on a true first run.
        """

        self.workspace = workspace
        self.scanner = scanner
        self.max_age = max_age
        self.idle_interval = idle_interval
        self.clock = clock
        self.on_clear = on_clear
        self._lock = threading.Lock()  # guards the dictionaries below, never a walk
        self._refresh_lock = threading.Lock()  # single-flight for every validation
        self._entries: dict[bool, Inventory] = {}
        self._validated_at: dict[bool, float | None] = {}
        self._requested: dict[bool, bool] = {}
        self._dirty: set[bool] = set()
        self._generation = 0  # bumped by clear(); a validation started earlier is stale
        self._serials: dict[bool, int] = {}  # bumped by every disk validation of a scope

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

    @staticmethod
    def _hashed(inventory: Inventory) -> bool:
        return all(record.sha256 for record in inventory.records)

    def _validate(self, include_vendor: bool, *, hash_files: bool, force: bool) -> Inventory:
        """Walk the disk and merge it with what is known; call with `_refresh_lock` held."""

        with self._lock:
            generation = self._generation
            previous = self._entries.get(include_vendor)
            other = self._entries.get(not include_vendor)
        if previous is None:
            previous = self._load(include_vendor)
        if previous is None:
            # The vendor scope is a superset of the default scope. Reuse
            # every overlapping digest when the owner toggles that view
            # instead of hashing the same thousand files a second time.
            previous = other or self._load(not include_vendor)
        snapshot = self.scanner(self.workspace, include_vendor=include_vendor, hash_files=False)
        inventory = None
        if previous is not None and not force and self._same_snapshot(snapshot, previous):
            if not hash_files or self._hashed(previous):
                inventory = previous
        changed = inventory is None
        if inventory is None:
            inventory = self._merge_hashes(snapshot, previous, hash_files=hash_files, force=force)
        with self._lock:
            self._entries[include_vendor] = inventory
            self._validated_at[include_vendor] = self.clock()
            self._serials[include_vendor] = self._serials.get(include_vendor, 0) + 1
            self._requested[include_vendor] = False
            if generation == self._generation:
                self._dirty.discard(include_vendor)
        if changed:
            # Only a changed inventory is written: a background tick must not
            # rewrite the JSON into a synced folder every few seconds.
            self._store(inventory)
        return inventory

    def get(
        self,
        *,
        include_vendor: bool,
        hash_files: bool = True,
        force: bool = False,
        fresh: bool = False,
    ) -> Inventory:
        """Return the inventory for one scope.

        `fresh=True` asks for a synchronous disk validation even in snapshot
        mode; mutation paths use it so a plan is never built from a snapshot.
        """

        if self.max_age <= 0 or force or fresh:
            with self._refresh_lock:
                return self._validate(include_vendor, hash_files=hash_files, force=force)
        with self._lock:
            self._requested[include_vendor] = True
            current = self._entries.get(include_vendor)
            dirty = include_vendor in self._dirty
        if dirty:
            current = None
        elif current is None:
            # First use since the process started: adopt the persisted
            # inventory at once and let the ticker validate it.
            loaded = self._load(include_vendor)
            if loaded is not None:
                with self._lock:
                    if include_vendor not in self._entries and include_vendor not in self._dirty:
                        self._entries[include_vendor] = loaded
                        self._validated_at[include_vendor] = None
                    current = self._entries.get(include_vendor)
                    if include_vendor in self._dirty:
                        current = None
        if current is not None and (not hash_files or self._hashed(current)):
            return current
        with self._refresh_lock:
            # Another request may have validated this scope while we waited.
            with self._lock:
                current = self._entries.get(include_vendor)
                usable = (
                    current is not None
                    and include_vendor not in self._dirty
                    and self._validated_at.get(include_vendor) is not None
                    and (not hash_files or self._hashed(current))
                )
            if usable:
                return current  # type: ignore[return-value]
            return self._validate(include_vendor, hash_files=hash_files, force=False)

    def serial(self, include_vendor: bool) -> int:
        """How many disk validations this scope has had in this process.

        An unchanged disk keeps the same `Inventory` object, so identity alone
        cannot tell a memo that the disk was looked at again. Files outside the
        inventory, such as metadata sidecars, key their re-check on this.
        """

        with self._lock:
            return self._serials.get(include_vendor, 0)

    def refresh(self, include_vendor: bool) -> bool:
        """Validate one loaded scope now; skip when a validation is already running."""

        with self._lock:
            if include_vendor not in self._entries:
                return False
        if not self._refresh_lock.acquire(blocking=False):
            return False
        try:
            self._validate(include_vendor, hash_files=True, force=False)
            return True
        except Exception:
            logger.exception("inventory refresh failed (include_vendor=%s)", include_vendor)
            return False
        finally:
            self._refresh_lock.release()

    def due(self, include_vendor: bool, now: float | None = None) -> bool:
        with self._lock:
            if include_vendor not in self._entries:
                return False
            validated_at = self._validated_at.get(include_vendor)
            requested = self._requested.get(include_vendor, False)
        if validated_at is None:
            return True  # adopted from disk, never validated in this process
        current = self.clock() if now is None else now
        return is_due(
            age=current - validated_at,
            interval=self.max_age,
            idle_interval=self.idle_interval,
            requested=requested,
        )

    def refresh_due(self) -> None:
        if self.max_age <= 0:
            return
        with self._lock:
            scopes = tuple(self._entries)
        for include_vendor in scopes:
            if self.due(include_vendor):
                self.refresh(include_vendor)

    def clear(self) -> None:
        """Forget that the snapshot is current: the next `get()` validates the disk.

        Both scopes are marked, loaded or not, so a scope first used after a
        mutation is validated rather than adopted from a stale persisted file.
        """

        with self._lock:
            self._generation += 1
            self._dirty.update((False, True))
            if self.max_age <= 0:
                self._entries.clear()
        if self.on_clear is not None:
            self.on_clear()


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


def preview_version(mtime_ns: int, size: int) -> str:
    """The `v` key a preview URL carries: the file's stat plus the renderer.

    A browser may keep a response to a URL bearing this key for a year,
    because any change to the file or to the renderer yields a different key
    and therefore a different URL. The server re-checks the key against a
    fresh stat before promising that; see `preview_image`.
    """

    return f"{mtime_ns:x}-{size:x}-r{geometry_preview.RENDERER_VERSION}"


PREVIEW_STRIP_SIZE = 6
PROJECT_EXTENSIONS = frozenset({".ipj"})


STRIP_EXPORT_EXTENSIONS = frozenset({".stl", ".step", ".stp", ".3mf"})


def strip_rank(record, top_level=None, rendered=None) -> int | None:
    """How well a file represents its folder on a card; lower is better.

    0: an assembly no other document references (a top-level assembly);
    1: any other assembly; 2: a part; 3: another Inventor document; 4: an
    export (STL, STEP, 3MF) whose render is already cached. None: not a
    representative, only a top-up for a short strip.
    """

    suffix = record.suffix.casefold()
    if suffix == ".iam":
        return 0 if top_level is not None and top_level(record) else 1
    if suffix == ".ipt":
        return 2
    if suffix in INVENTOR_EXTENSIONS:
        return 3
    if suffix in STRIP_EXPORT_EXTENSIONS and rendered is not None and rendered(record):
        return 4
    return None


def folder_strips(
    records,
    current: str,
    limit: int = PREVIEW_STRIP_SIZE,
    leading=(),
    top_level=None,
    rendered=None,
) -> dict[str, list]:
    """Preview picks for the card of each immediate child folder of `current`.

    Manual picks come first: the `leading` records (the heroes, then the
    featured files, each in path order) open the strip of the child folder
    they sit anywhere below, in the order given. The rest go round-robin, so
    a card shows what kinds of thing its folder holds rather than six files
    of its first subfolder: each round takes the best remaining file (see
    `strip_rank`; larger first, then path order) from each of the card
    folder's own subfolders in name order, then from its direct files. A
    subfolder a leading record came from sits out the rounds it has covered.
    Files with no rank only top a short strip up. No record is repeated.

    `top_level(record)` says whether an assembly is referenced by nothing;
    `rendered(record)` whether an export's render is cached. One pass over
    the inventory records; returns child-folder path -> records.
    """

    prefix = "" if current == "." else f"{current}/"
    offset = len(prefix)

    def place(path: str) -> tuple[str, str] | None:
        """(card folder, its subfolder or "" for a direct file), or None."""

        if not path.startswith(prefix):
            return None
        slash = path.find("/", offset)
        if slash == -1:
            return None  # a direct file of `current`
        below = path.find("/", slash + 1)
        return path[:slash], "" if below == -1 else path[:below]

    first: dict[str, list] = {}
    taken: dict[str, dict[str, int]] = {}
    for record in leading:
        where = place(record.path)
        if where is None:
            continue
        child, group = where
        first.setdefault(child, []).append(record)
        counts = taken.setdefault(child, {})
        counts[group] = counts.get(group, 0) + 1
    skip = {record.path for items in first.values() for record in items}
    ranked: dict[str, dict[str, list]] = {}
    other: dict[str, list] = {}
    for position, record in enumerate(records):
        where = place(record.path)
        if where is None or record.path in skip:
            continue
        child, group = where
        rank = strip_rank(record, top_level, rendered)
        if rank is None:
            items = other.setdefault(child, [])
            if len(items) < limit:
                items.append(record)
            continue
        ranked.setdefault(child, {}).setdefault(group, []).append(
            (rank, -record.size, position, record)
        )

    strips: dict[str, list] = {}
    for child in first.keys() | ranked.keys() | other.keys():
        picks = first.get(child, [])[:limit]
        groups = {
            group: [item[-1] for item in sorted(items, key=lambda item: item[:3])[:limit]]
            for group, items in ranked.get(child, {}).items()
        }
        order = sorted((group for group in groups if group), key=str.casefold)
        if "" in groups:
            order.append("")
        counts = dict(taken.get(child, {}))
        cursors = dict.fromkeys(order, 0)
        rounds = 0
        while len(picks) < limit and any(cursors[group] < len(groups[group]) for group in order):
            rounds += 1
            for group in order:
                if len(picks) >= limit:
                    break
                if counts.get(group, 0) >= rounds or cursors[group] >= len(groups[group]):
                    continue
                picks.append(groups[group][cursors[group]])
                cursors[group] += 1
                counts[group] = counts.get(group, 0) + 1
        strips[child] = (picks + other.get(child, []))[:limit]
    return strips


def _parent_label(path: str) -> str:
    return _windows_path(path.rsplit("/", 1)[0]) if "/" in path else "the workspace root"


def file_signals(inventory: Inventory) -> dict[str, tuple[dict, ...]]:
    """Per-path catalog signals derived from one inventory, without a new scan.

    Kinds reuse the Duplicates and Doctor palette: `collision`, `exact`,
    `unverified`, and `renamed` describe copies; `generic` and `newer`
    describe the name. Each is one short word badge under the tile's size
    line, with `text` as its tooltip. `newer` is filesystem evidence only:
    another same-named file has a later mtime.
    """

    found: dict[str, list[dict]] = {}

    def add(path: str, kind: str, text: str) -> None:
        found.setdefault(path, []).append({"kind": kind, "word": SIGNAL_WORDS[kind], "text": text})

    for group in inventory.filename_groups:
        others = len(group.records) - 1
        plural = "s" if others != 1 else ""
        for record in group.records:
            if group.kind == "collision":
                add(record.path, "collision", f"Same filename, different bytes: {others} other file{plural}")
            elif group.kind == "exact":
                add(record.path, "exact", f"Identical copy: {others} other file{plural} with this name and bytes")
            else:
                add(record.path, "unverified", f"Same filename as {others} other file{plural}; bytes not compared yet")
            if group.kind == "collision":
                newer = [other for other in group.records if other.mtime_ns > record.mtime_ns]
                if newer:
                    newest = max(newer, key=lambda other: other.mtime_ns)
                    add(
                        record.path,
                        "newer",
                        f"A newer file with this name exists at {_parent_label(newest.path)}",
                    )
    for group in inventory.renamed_groups:
        others = len(group.records) - 1
        plural = "s" if others != 1 else ""
        for record in group.records:
            if group.characterization == "newver":
                text = "newVer pair: same bytes under a .newVer name; origin unproven"
            else:
                text = f"Same bytes as {others} file{plural} with a different name"
            add(record.path, "renamed", text)
    for record in inventory.records:
        if _is_generic_cad_name(record.name):
            add(record.path, "generic", "Generic name that says nothing about the part")
    return {path: tuple(items) for path, items in found.items()}


# Every signal is one badge: a short lowercase word in a small tinted box
# (fleet's badge vocabulary), in a row under the tile's size line, in this
# order. The legend lists all of them in the same order on every page,
# whether or not a page shows each one, so the legend never changes size.
# No tile carries a coloured edge. Each row is (kind, badge word, meaning).
SIGNAL_LEGEND = (
    ("collision", "clash", "Same name, different bytes"),
    ("exact", "copy", "Identical copy elsewhere"),
    ("renamed", "renamed", "Same bytes, other name"),
    ("unverified", "unhashed", "Same name, bytes not compared"),
    ("generic", "generic", "Generic name"),
    ("newer", "newer", "Newer file with this name exists"),
    ("sourced", "sourced", "Named in a sourcing option"),
    ("hero", "main", "Main assembly"),
    ("featured", "featured", "Featured on folder card"),
)
SIGNAL_WORDS = {kind: word for kind, word, _text in SIGNAL_LEGEND}
SIGNAL_ORDER = {kind: position for position, (kind, _word, _text) in enumerate(SIGNAL_LEGEND)}
HERO_SIGNAL = {"kind": "hero", "word": SIGNAL_WORDS["hero"], "text": "Main assembly"}
FEATURED_SIGNAL = {"kind": "featured", "word": SIGNAL_WORDS["featured"], "text": "Featured"}


SOURCED_SIGNAL = {"kind": "sourced", "word": SIGNAL_WORDS["sourced"], "text": "Named in a sourcing option"}


def sourced_signal(titles) -> dict:
    """The `sourced` mark on the part page, which names the options (no Sourced fact there)."""

    return {
        "kind": "sourced",
        "word": SIGNAL_WORDS["sourced"],
        "text": "Sourcing option: " + "; ".join(titles),
    }


def attachment_version(mtime_ns: int, size: int) -> str:
    """The `v` key of an attachment URL: the file's own stat, nothing else."""

    return f"{mtime_ns:x}-{size:x}"


#: Extra room over the attachment cap for the multipart envelope and token.
ATTACH_ENVELOPE_BYTES = 64 * 1024


def ordered_signals(marks) -> tuple[dict, ...]:
    """Marks in legend order, so a tile's badges read the same way everywhere."""

    return tuple(sorted(marks, key=lambda mark: SIGNAL_ORDER.get(mark["kind"], len(SIGNAL_ORDER))))


def tile_anchor(path: str) -> str:
    """The fragment id of a file's catalog tile, so a redirect can land on it."""

    return f"file-{_anchor(path)}"


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
    refresh_seconds: float = 0.0,
) -> Flask:
    """Build the viewer.

    `refresh_seconds == 0` validates the disk on every request (tests rely on
    this). `refresh_seconds > 0` serves every read-only page from in-memory
    snapshots that a background ticker refreshes; mutations still check the
    live disk and then invalidate the snapshots.
    """

    root = Path(workspace or Path.cwd()).resolve()
    app = Flask(__name__)
    app.config.update(WORKSPACE=root, VERSION=__version__, FORM_TOKEN=secrets.token_urlsafe(32))
    cache = InventoryCache(root, scanner, max_age=max(refresh_seconds, 0.0))
    previews = PreviewCache(root)
    references = ReferenceCache()
    catalog_metadata: dict[str, tuple[int, int, DocumentMeta]] = {}
    catalog_metadata_lock = threading.RLock()
    catalog_indexes: dict[bool, tuple[Inventory, list[dict]]] = {}
    catalog_indexes_lock = threading.Lock()
    catalog_signals: dict[bool, tuple[Inventory, dict[str, tuple[dict, ...]]]] = {}
    # Designated main assemblies and featured files: per scope, the inventory
    # and validation serial they were found for; per sidecar, the two flags
    # read at a (mtime, size).
    hero_memo: dict[
        bool, tuple[Inventory, int, tuple[tuple[FileRecord, ...], tuple[FileRecord, ...]]]
    ] = {}
    hero_flags: dict[str, tuple[int, int, bool, bool]] = {}
    # Folder-card strips per (scope, folder), valid while the inventory, the
    # where-used index, and the flag lookup are the same objects.
    strip_memo: dict[tuple[bool, str], tuple[object, object, object, dict[str, list]]] = {}
    hero_lock = threading.Lock()
    # Every sourcing note in the archive, per scope, for the inventory and
    # validation serial it was read at: folder -> (options, problems), and
    # CAD path -> the titles of the options naming it in `for`.
    sourcing_memo: dict[bool, tuple[Inventory, int, dict]] = {}
    standard_memo: dict[str, tuple] = {}
    standard_memo_lock = threading.Lock()
    app.extensions["pihti_inventory_cache"] = cache
    app.extensions["pihti_preview_cache"] = previews
    app.extensions["pihti_reference_cache"] = references

    whereused_snapshot: Snapshot | None = None
    locations_snapshot: Snapshot | None = None
    merges_snapshot: Snapshot | None = None
    if refresh_seconds > 0:
        whereused_snapshot = Snapshot(
            lambda: build_index(root, cache=references),
            interval=refresh_seconds,
            name="whereused_index",
        )
        locations_snapshot = Snapshot(
            lambda: filename_locations(root),
            interval=refresh_seconds,
            name="locations",
        )
        merges_snapshot = Snapshot(
            lambda: tuple(merge_reader(root)),
            interval=max(refresh_seconds, 60.0),
            idle_interval=max(refresh_seconds, 60.0) * 5,
            name="merges",
        )
        derived = (whereused_snapshot, locations_snapshot, merges_snapshot)

        def invalidate_derived() -> None:
            for snapshot in derived:
                snapshot.invalidate()

        cache.on_clear = invalidate_derived
        ticker = Ticker([cache, *derived], period=refresh_seconds)
        app.extensions["pihti_snapshots"] = {
            snapshot.name: snapshot for snapshot in derived
        }

        @app.before_request
        def start_ticker():
            # Lazily, so constructing an app in a test never spawns a thread.
            if "pihti_ticker" not in app.extensions:
                app.extensions["pihti_ticker"] = ticker
            ticker.start()

    def _current_index():
        if whereused_snapshot is not None:
            return whereused_snapshot.get()
        return build_index(root, cache=references)

    def _current_locations() -> dict[str, tuple[str, ...]]:
        if locations_snapshot is not None:
            return locations_snapshot.get()
        return filename_locations(root)

    def _current_merges() -> tuple[PullRequestMerge, ...]:
        if merges_snapshot is not None:
            return merges_snapshot.get()
        return tuple(merge_reader(root))
    app.jinja_env.filters["filesize"] = _filesize
    app.jinja_env.filters["winpath"] = _windows_path
    app.jinja_env.filters["filetime"] = _filetime
    app.jinja_env.tests["newver_name"] = _is_newver_name
    app.jinja_env.tests["generic_cad_name"] = _is_generic_cad_name
    app.jinja_env.globals["RENAMEABLE_EXTENSIONS"] = RENAMEABLE_EXTENSIONS
    app.jinja_env.globals["SOURCING_STATUSES"] = STATUS_VALUES

    def preview_url(item) -> str:
        """`/preview/<path>?v=<key>` for a FileRecord, a dict/obj with `path`, or a path.

        A record already carries its stat from the inventory snapshot; anything
        else is stat'ed here. A file that cannot be stat'ed gets the unversioned
        URL, which the route serves with `no-cache` as before.
        """

        mtime_ns = getattr(item, "mtime_ns", None)
        size = getattr(item, "size", None)
        if isinstance(item, str):
            path = item
        elif isinstance(item, dict):
            path = item.get("path", "")
        else:
            path = getattr(item, "path", "")
        if mtime_ns is None or size is None:
            target = workspace_file(root, path)
            try:
                stat = target.stat() if target is not None else None
            except OSError:
                stat = None
            if stat is None:
                return url_for("preview_image", relative_path=path)
            mtime_ns, size = stat.st_mtime_ns, stat.st_size
        return url_for(
            "preview_image", relative_path=path, v=preview_version(mtime_ns, size)
        )

    app.jinja_env.globals["preview_url"] = preview_url

    @app.after_request
    def no_store(response):
        # `/preview/...` is exempt. Every other page reports live filesystem
        # state that a cached copy would misreport, but a preview is keyed by
        # the file's own modification time and carries an ETag and
        # Last-Modified, so a conditional request is exact rather than
        # optimistic. A rendered STEP costs seconds; making the browser refetch
        # 280 of them on every catalog visit would defeat the disk cache.
        if request.endpoint in {"preview_image", "git_history_preview", "sourcing_file"}:
            return response
        # A plain catalog page may be reused for five seconds so a page the
        # browser prefetched on hover serves the click that follows. The page
        # is rendered from an inventory snapshot the ticker refreshes on about
        # that period anyway; search results and the post-save view stay live.
        if (
            request.endpoint == "catalog"
            and request.method == "GET"
            and response.status_code == 200
            and "q" not in request.args
            and "saved" not in request.args
            and "hero" not in request.args
            and "featured" not in request.args
        ):
            response.headers["Cache-Control"] = "private, max-age=5"
            return response
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/duplicates")
    def duplicates():
        return render_template("duplicates.html", workspace=root.name, version=__version__)

    @app.get("/doctor")
    def doctor():
        inventory = cache.get(include_vendor=False)
        index = _current_index()
        locations = _current_locations()
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
        standard_candidates = _standard_candidates(inventory, index, locations)
        return render_template(
            "doctor.html",
            version=__version__,
            workspace=root.name,
            standard_candidates=standard_candidates,
            standard_movable=sum(
                item.plan.outcome == MOVE for item in standard_candidates
            ),
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
        index = _current_index()
        locations = _current_locations()
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
        locations = _current_locations()
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
        index = _current_index()
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

    def _standard_candidates(inventory: Inventory, index, locations) -> tuple:
        # Snapshots are swapped whole, so identity is an exact memo key: the
        # iProperty pass and the plans are rebuilt only when one of them changed.
        with standard_memo_lock:
            cached = standard_memo.get("value")
            if (
                cached is not None
                and cached[0] is inventory
                and cached[1] is index
                and cached[2] is locations
            ):
                return cached[3]

        def fields_for(record):
            meta = _catalog_document_meta(record)
            return meta.fields if meta is not None and meta.ok else None

        candidates = find_standard_candidates(
            root,
            inventory.records,
            fields_for=fields_for,
            index=index,
            locations=locations,
        )
        with standard_memo_lock:
            standard_memo["value"] = (inventory, index, locations, candidates)
        return candidates

    standard_groups = {
        MOVE: ("Ready to move", "Unique name", "Nothing else in the workspace carries the name."),
        IDENTICAL: (
            "Already in the library",
            "Same bytes at the destination",
            "The library already holds these bytes under this name; "
            "the stray copy can go to the recoverable quarantine.",
        ),
        CONFLICT: (
            "Name collision",
            "Refused",
            "The name exists elsewhere, so a move would leave Inventor two candidates. "
            "Settle it in Collision Doctor first.",
        ),
        REFUSED: ("Refused", "Cannot move", "The move breaks a path or filename rule."),
    }

    def _standard_confirm(plan) -> str:
        if plan.outcome == MOVE:
            count = len(plan.referrers)
            return (
                f"Move this part into the library?\n\n{_windows_path(plan.source_path)}\n"
                f"→ {_windows_path(plan.destination_path)}\n\n"
                f"{count} referring document{'s' if count != 1 else ''} will find it again "
                "by filename. The move is recorded under Renames."
            )
        return (
            "Move only this copy to recoverable quarantine?\n\n"
            f"{_windows_path(plan.source_path)}\n\n"
            f"Surviving copy:\n{_windows_path(plan.survivor_path)}\n\n"
            "Continue only after checking Inventor references."
        )

    def _standard_parts_context(*, error: str | None = None) -> dict:
        inventory = cache.get(include_vendor=False)
        candidates = _standard_candidates(inventory, _current_index(), _current_locations())
        groups = []
        order = 0
        for outcome in OUTCOMES:
            rows = []
            for candidate in candidates:
                if candidate.plan.outcome != outcome:
                    continue
                plan = candidate.plan
                rows.append(
                    {
                        "order": order,
                        "path": candidate.path,
                        "name": candidate.name,
                        "record": candidate.record,
                        "folder": plan.source_folder,
                        "evidence": candidate.evidence.items,
                        "plan": plan,
                        "confirm": _standard_confirm(plan) if plan.actionable else "",
                    }
                )
                order += 1
            if rows:
                title, kicker, intro = standard_groups[outcome]
                groups.append(
                    {"key": outcome, "title": title, "kicker": kicker, "intro": intro, "rows": rows}
                )
        destination = root / DEFAULT_DESTINATION
        try:
            library_count = sum(
                1 for path in destination.iterdir() if path.suffix.casefold() == ".ipt"
            )
        except OSError:
            library_count = 0
        toast = ""
        moved_id = request.args.get("moved", "")
        if moved_id:
            entry = next((item for item in read_ledger(root) if item.id == moved_id), None)
            if entry is not None:
                toast = (
                    f"Moved {entry.new_name} to {_windows_path(entry.new_folder)}. "
                    f"Ledger entry {entry.id} is listed under Renames."
                )
        quarantined = request.args.get("quarantined", "")
        if quarantined:
            event = next(
                (
                    item
                    for item in read_quarantine_manifests(root)
                    if str(item.get("group_id", "")) == quarantined
                ),
                None,
            )
            if event is not None:
                moved = ", ".join(
                    _windows_path(str(item.get("path", ""))) for item in event.get("files", [])
                )
                toast = (
                    f"Quarantined {moved}. Surviving copy: "
                    f"{_windows_path(str(event.get('keep_path', '')))}. Restore it from Removed."
                )
        return {
            "version": __version__,
            "workspace": root.name,
            "groups": groups,
            "candidate_count": len(candidates),
            "destination": DEFAULT_DESTINATION,
            "library_count": library_count,
            "form_token": app.config["FORM_TOKEN"],
            "error": error,
            "toast": toast,
        }

    @app.get("/doctor/standard-parts")
    def doctor_standard_parts():
        return render_template("doctor_standard_parts.html", **_standard_parts_context())

    def _standard_error(message: str, status: int):
        return render_template(
            "doctor_standard_parts.html", **_standard_parts_context(error=message)
        ), status

    def _fresh_standard_plan(relative_path: str):
        """Rebuild one plan from live disk: evidence, where-used, collision map."""

        target = workspace_file(root, relative_path)
        if target is None:
            raise StandardMoveError("that file is no longer in the workspace")
        relative = target.relative_to(root).as_posix()
        meta = read_inventor_document(target)
        evidence = is_standard_candidate(relative, meta.fields if meta.ok else None)
        if evidence is None:
            raise StandardMoveError(f"{target.name} is no longer a standard-part candidate")
        return plan_standard_move(
            root,
            relative,
            index=build_index(root, cache=references),
            locations=filename_locations(root),
            evidence=evidence.labels,
        )

    def _reviewed_standard_plan(expected_outcome: str):
        """The live plan for the posted row, or the error response that refuses it."""

        try:
            plan = _fresh_standard_plan(request.form.get("path", ""))
        except StandardMoveError as exc:
            return None, _standard_error(str(exc), 409)
        if not secrets.compare_digest(request.form.get("signature", ""), plan.signature):
            return None, _standard_error(
                f"{plan.name} changed since this page was drawn; review the row again", 409
            )
        if plan.outcome != expected_outcome:
            return None, _standard_error(plan.reason or f"{plan.name} cannot be moved", 409)
        return plan, None

    @app.post("/doctor/standard-parts/move")
    def standard_part_move():
        guard = _guard(request)
        if guard is not None:
            return guard
        plan, refusal = _reviewed_standard_plan(MOVE)
        if refusal is not None:
            return refusal
        if not _flag(request.form.get("confirmed")):
            return _standard_error(f"confirm the move of {plan.name} first", 400)
        try:
            result = execute_standard_move(root, plan, confirmed=True)
        except (StandardMoveError, OSError) as exc:
            return _standard_error(str(exc), 409)
        cache.clear()
        return redirect(url_for("doctor_standard_parts", moved=result.entry.id))

    @app.post("/doctor/standard-parts/quarantine")
    def standard_part_quarantine():
        guard = _guard(request)
        if guard is not None:
            return guard
        plan, refusal = _reviewed_standard_plan(IDENTICAL)
        if refusal is not None:
            return refusal
        if not _flag(request.form.get("references_checked")):
            return _standard_error("Inventor references must be checked first", 400)
        if request.form.get("survivor", "").casefold() != plan.survivor_path.casefold():
            return _standard_error(
                f"the surviving copy is {_windows_path(plan.survivor_path)}; review the row again",
                409,
            )
        try:
            result = execute_standard_move(root, plan, confirmed=True)
        except (StandardMoveError, ValueError, OSError) as exc:
            return _standard_error(str(exc), 409)
        cache.clear()
        return redirect(
            url_for("doctor_standard_parts", quarantined=result.quarantine.group_id)
        )

    @app.get("/")
    def index():
        return redirect(url_for("catalog"))

    @app.post("/markdown/preview")
    def markdown_preview():
        """Render unsaved local-note Markdown without writing workspace data.

        A sourcing editor names its folder, so the preview shows the note's
        attachments the way the saved note will.
        """
        text = request.form.get("text", "")
        folder = request.form.get("sourcing", "")
        if folder:
            target = _sourcing_target(folder)
            if target is not None:
                return jsonify(html=_render_sourcing(text, target[1]))
        return jsonify(html=render_markdown(text))

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
        merges = _current_merges()
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
        inventory = cache.get(include_vendor=include_vendor, fresh=True)
        plan = plan_merge_exact_cleanup(inventory, merge)
        if not secrets.compare_digest(str(payload.get("signature", "")), plan.signature):
            return jsonify({"error": "cleanup plan changed; run the dry preview again"}), 409
        try:
            execution = execute_cleanup(root, plan, references_checked=True)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        cache.clear()
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
        inventory = cache.get(include_vendor=include_vendor, fresh=True)
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
        cache.clear()
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
        inventory = cache.get(include_vendor=include_vendor, fresh=True)
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
        cache.clear()
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
        supplied = request.args.get("v", "")
        if (
            preview is not None
            and supplied
            and supplied == preview_version(stat.st_mtime_ns, stat.st_size)
        ):
            # The URL names this exact file state, so it can never go stale:
            # a resave changes the stat and therefore the URL. A placeholder
            # is never promised, because installing a preview extra turns it
            # into a real image without touching the file.
            response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        else:
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
        locations = _current_locations()
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
        # Inventories are immutable and swapped whole, so identity is an exact
        # key: the folder tree is rebuilt only when the inventory changed.
        with catalog_indexes_lock:
            cached = catalog_indexes.get(inventory.include_vendor)
            if cached is not None and cached[0] is inventory:
                return cached[1]
        index = _build_catalog_index(inventory)
        with catalog_indexes_lock:
            catalog_indexes[inventory.include_vendor] = (inventory, index)
        return index

    def _catalog_signals(inventory: Inventory) -> dict[str, tuple[dict, ...]]:
        # Same identity memo as the folder index: rebuilt once per inventory.
        with catalog_indexes_lock:
            cached = catalog_signals.get(inventory.include_vendor)
            if cached is not None and cached[0] is inventory:
                return cached[1]
        signals = file_signals(inventory)
        with catalog_indexes_lock:
            catalog_signals[inventory.include_vendor] = (inventory, signals)
        return signals

    def _catalog_flags(
        inventory: Inventory,
    ) -> tuple[tuple[FileRecord, ...], tuple[FileRecord, ...]]:
        """Records whose sidecar says `hero: true`, then `featured: true`, in path order.

        Both flags come from one pass. Memoized per inventory object and
        validation serial, so it is redone once per snapshot refresh. That
        pass is one `stat` per record; a sidecar is read only when its size or
        modification time changed.
        """

        serial = cache.serial(inventory.include_vendor)
        with hero_lock:
            cached = hero_memo.get(inventory.include_vendor)
            if cached is not None and cached[0] is inventory and cached[1] == serial:
                return cached[2]
        heroes: list[FileRecord] = []
        featured: list[FileRecord] = []
        for record in inventory.records:
            companion = root / (record.path + ".md")
            try:
                stat = os.stat(companion)
            except OSError:
                continue
            key = (stat.st_mtime_ns, stat.st_size)
            with hero_lock:
                known = hero_flags.get(record.path)
            if known is not None and known[:2] == key:
                flags = known[2:]
            else:
                try:
                    sidecar = read_sidecar(companion)
                    flags = (bool(sidecar and sidecar.hero), bool(sidecar and sidecar.featured))
                except (SidecarError, OSError, UnicodeDecodeError):
                    flags = (False, False)
                with hero_lock:
                    hero_flags[record.path] = (*key, *flags)
            if flags[0]:
                heroes.append(record)
            if flags[1]:
                featured.append(record)

        def by_path(items: list[FileRecord]) -> tuple[FileRecord, ...]:
            return tuple(sorted(items, key=lambda record: record.path.casefold()))

        found = (by_path(heroes), by_path(featured))
        with hero_lock:
            hero_memo[inventory.include_vendor] = (inventory, serial, found)
        return found

    def _catalog_strips(
        inventory: Inventory,
        current: str,
        heroes: tuple[FileRecord, ...],
        featured: tuple[FileRecord, ...],
    ) -> dict[str, list]:
        """Folder-card strips for the children of `current`, memoised per snapshot.

        Manual first: the heroes below each card, then the featured files,
        then the ranked round-robin of `folder_strips`, which asks the
        where-used snapshot whether an assembly is top-level.
        """

        index = _current_index()
        flags = _catalog_flags(inventory)
        key = (inventory.include_vendor, current)
        with hero_lock:
            cached = strip_memo.get(key)
        if (
            cached is not None
            and cached[0] is inventory
            and cached[1] is index
            and cached[2] is flags
        ):
            return cached[3]
        hero_paths = {record.path for record in heroes}
        leading = (*heroes, *(record for record in featured if record.path not in hero_paths))
        store = geometry_preview.preview_store(root)

        def top_level(record: FileRecord) -> bool:
            return not index.referring(record.name)

        def rendered(record: FileRecord) -> bool:
            target = root / record.path
            cache_key = geometry_preview.cache_key(target, record.mtime_ns, record.size)
            return geometry_preview.cache_path(store, cache_key).is_file()

        strips = folder_strips(
            inventory.records, current, leading=leading, top_level=top_level, rendered=rendered
        )
        with hero_lock:
            strip_memo[key] = (inventory, index, flags, strips)
        return strips

    def _forget_hero(relative: str) -> None:
        with hero_lock:
            hero_memo.clear()
            strip_memo.clear()
            hero_flags.pop(relative, None)

    def _build_catalog_index(inventory: Inventory) -> list[dict]:
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

    def _folder_card(item: dict, strip: list | None = None) -> dict:
        note = _read_catalog_note(item["name"])
        return {
            **item,
            "label": item["name"].rsplit("/", 1)[-1],
            "excerpt": note.excerpt if note and not note.generated else "",
            "strip": strip or [],
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

    def _catalog_file(
        record: FileRecord,
        index=None,
        signals=None,
        heroes=frozenset(),
        featured=frozenset(),
        sourced=None,
    ) -> dict:
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
        # Hover/keyboard details: rendered only when something exists beyond
        # the name, size, and chips the tile already shows.
        mass = mass_properties(fields).get("mass") if fields else None
        used_in = index.referring(record.name) if index is not None else ()
        marks = signals.get(record.path, ()) if signals else ()
        is_hero = record.path in heroes
        if is_hero:
            marks = (*marks, HERO_SIGNAL)
        if record.path in featured:
            marks = (*marks, FEATURED_SIGNAL)
        sourced_titles = sourced.get(record.path.casefold(), ()) if sourced else ()
        if sourced_titles:
            # The titles go in the Sourced fact below, so the badge row states
            # only what the mark is, as the legend does.
            marks = (*marks, SOURCED_SIGNAL)
        marks = ordered_signals(marks)
        details: list[tuple[str, str]] = []
        if description or mass is not None or used_in or marks:
            if sourced_titles:
                details.append(("Sourced", "; ".join(sourced_titles)))
            if description:
                details.append(("Description", description))
            if part_number:
                details.append(("Part number", part_number))
            if material:
                details.append(("Material", material))
            if mass is not None:
                details.append(("Mass", f"{mass:.4g} g"))
            details.append(("Modified", _filetime(record.mtime_ns)[:16]))
        return {
            "anchor": tile_anchor(record.path),
            "hero": is_hero,
            "featured": record.path in featured,
            "folder": record.path.rsplit("/", 1)[0] if "/" in record.path else ".",
            "description": description,
            "details": details,
            "used_in": used_in if details else (),
            "signals": marks,
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

        project_files: list[dict] = []
        heroes, featured = _catalog_flags(inventory)
        hero_paths = frozenset(record.path for record in heroes)
        featured_paths = frozenset(record.path for record in featured)
        hero_records: list[FileRecord] = []
        if query:
            folded = query.casefold()
            matching = [record for record in inventory.records if folded in record.path.casefold()]
            child_folders: list[dict] = []
            records = matching[:show]
            total = len(matching)
        else:
            strips = (
                _catalog_strips(inventory, current, heroes, featured)
                if current_stats["children"]
                else {}
            )
            child_folders = [
                _folder_card(by_name[name], strips.get(name))
                for name in current_stats["children"]
            ]
            direct = [
                record
                for record in inventory.records
                if (record.path.rsplit("/", 1)[0] if "/" in record.path else ".") == current
            ]
            if current == ".":
                # The Inventor project file is what the owner opens, not a part
                # to browse: it stands in the context rail, not the file grid.
                project_files = [
                    {"record": record, "absolute": str(root / record.path)}
                    for record in direct
                    if record.suffix.casefold() in PROJECT_EXTENSIONS
                ]
                direct = [
                    record for record in direct if record.suffix.casefold() not in PROJECT_EXTENSIONS
                ]
            # Main assemblies lead in a row of their own and are not repeated
            # among the files: every one in the archive at the root, the
            # folder's own below it.
            hero_records = (
                list(heroes)
                if current == "."
                else [record for record in direct if record.path in hero_paths]
            )
            direct = [record for record in direct if record.path not in hero_paths]
            records = direct[:show]
            total = len(direct)

        where_used = _current_index() if records or hero_records else None
        signals = _catalog_signals(inventory)
        sourcing_index = _sourcing_index(inventory)
        sourced = sourcing_index["sourced"]
        hero_files = [
            _catalog_file(record, where_used, signals, hero_paths, featured_paths, sourced)
            for record in hero_records
        ]
        files = [
            _catalog_file(record, where_used, signals, hero_paths, featured_paths, sourced)
            for record in records
        ]
        sourcing_line = None
        if current != "." and not query:
            options, problems = sourcing_index["folders"].get(current, ([], []))
            sourcing_line = {
                "summary": summary_line(options, problems),
                "url": url_for("sourcing_folder", relative_folder=current),
                "add_url": url_for("sourcing_new", relative_folder=current),
            }

        note = _read_catalog_note(current)
        note_text = _note_display_text(note)
        return {
            "version": __version__,
            "inventory": inventory,
            "file_count": len(inventory.records),
            "folder_count": max(0, len(index) - 1),
            "path": current,
            "name": "Catalog" if current == "." else current.rsplit("/", 1)[-1],
            "absolute_path": str(root if current == "." else root / current),
            "breadcrumbs": _breadcrumbs(current),
            "child_folders": child_folders,
            "hero_files": hero_files,
            "files": files,
            "shown": len(files),
            "result_total": total,
            "query": query,
            "next_show": min(total, show + 48),
            "has_more": len(files) < total,
            "subtree_count": current_stats["count"],
            "direct_count": current_stats["direct_count"],
            "project_files": project_files,
            "signal_legend": SIGNAL_LEGEND,
            "tree": folder_tree(index, current=current),
            "note": note,
            "workspace_summary": _workspace_summary() if current == "." else "",
            "note_text": note_text,
            "note_html": render_markdown(note_text),
            "note_rail_html": render_markdown(authored_part(note_text)),
            "note_error": None,
            "note_draft": None,
            "note_dialog_open": _flag(request.args.get("saved")),
            "saved": _flag(request.args.get("saved")),
            "form_token": app.config["FORM_TOKEN"],
            "include_vendor": inventory.include_vendor,
            "toast": _hero_toast(),
            "sourcing_line": sourcing_line,
        }

    def _hero_toast() -> str:
        name = request.args.get("file", "").replace("\\", "/").rsplit("/", 1)[-1]
        for key, label in ((HERO_KEY, "Hero"), (FEATURED_KEY, "Featured")):
            state = request.args.get(key, "")
            if name and state in {"set", "cleared"}:
                return f"{label} {state}: {name}"
        return ""

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
        # A move keeps the name, so the moved file itself is always a match;
        # what matters is whether anything else now carries that name.
        return {
            "is_move": entry.is_move,
            "move_present": any(
                path.casefold() == entry.new_path.casefold() for path in current_matches
            ),
            "move_others": tuple(
                path for path in current_matches if path.casefold() != entry.new_path.casefold()
            ),
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
        finally:
            _forget_hero(context["path"])
        return redirect(url_for("part_page", relative_path=context["path"], saved="1"))

    @app.post("/part/<path:relative_path>/hero")
    def part_hero(relative_path: str):
        """Set or clear `hero` in the file's sidecar, then return to where it was pressed."""

        return _toggle_flag(relative_path, HERO_KEY)

    @app.post("/part/<path:relative_path>/featured")
    def part_featured(relative_path: str):
        """Set or clear `featured` in the file's sidecar, then return to where it was pressed."""

        return _toggle_flag(relative_path, FEATURED_KEY)

    def _toggle_flag(relative_path: str, key: str):
        """Set or clear one sidecar flag from a form that states the wanted value.

        A repeated submit cannot flip it back. A missing sidecar is created
        seeded from iProperties, exactly as **Create metadata** does; an
        existing one changes by that one key.
        """

        guard = _guard(request)
        if guard is not None:
            return guard
        target = workspace_file(root, relative_path)
        if target is None:
            return render_template("_not_found.html", version=__version__, path=relative_path), 404
        relative = target.relative_to(root).as_posix()
        wanted = _flag(request.form.get(key))
        fields: dict[str, object] = {}
        if target.suffix.casefold() in INVENTOR_EXTENSIONS and not sidecar_path(target).is_file():
            fields = read_inventor_document(target).fields
        try:
            set_flag(sidecar_path(target), key, wanted, fields)
        except SidecarError as exc:
            context = _part_context(target)
            context.update(error=f"the sidecar was not changed: {exc}")
            return render_template("part.html", **context), 400
        except OSError as exc:
            context = _part_context(target)
            context.update(error=f"could not write the sidecar: {exc}")
            return render_template("part.html", **context), 500
        finally:
            _forget_hero(relative)
        state = {key: "set" if wanted else "cleared"}
        origin = request.form.get("origin", "")
        if origin == "part":
            return redirect(url_for("part_page", relative_path=relative, **state, file=relative))
        folder = "."
        if origin and origin != ".":
            origin_folder = workspace_folder(root, origin)
            if origin_folder is not None:
                folder = origin_folder.relative_to(root).as_posix()
        return redirect(
            url_for(
                "catalog",
                relative_folder=None if folder == "." else folder,
                **state,
                file=relative,
                include_vendor="1" if _flag(request.form.get("include_vendor")) else None,
                _anchor=tile_anchor(relative),
            )
        )

    def _folders(inventory: Inventory) -> list[tuple[str, list]]:
        grouped: dict[str, list] = {}
        for record in inventory.records:
            parent = record.path.rsplit("/", 1)[0] if "/" in record.path else "."
            grouped.setdefault(parent, []).append(record)
        return sorted(grouped.items(), key=lambda item: item[0].casefold())

    def _preview_size(target: Path, mtime_ns: int, size: int) -> tuple[int, int] | None:
        """Pixel size of an embedded Inventor preview, so it renders at 1x.

        Only Inventor documents are asked: their preview is read from the file
        and cached for the `/preview` request that follows. Rendered meshes are
        not rendered here just to learn their size.
        """

        if target.suffix.casefold() not in INVENTOR_EXTENSIONS:
            return None
        preview = previews.get(target, mtime_ns, size)
        data = preview.data if preview else b""
        if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
            return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        if data[:2] == b"BM" and len(data) >= 26:
            width = int.from_bytes(data[18:22], "little", signed=True)
            height = int.from_bytes(data[22:26], "little", signed=True)
            return abs(width), abs(height)
        return None

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
        # The part page shares the catalog shell: same grid, same tree rail
        # with the file's folder open, same header line.
        inventory = cache.get(include_vendor=False, hash_files=False)
        index = _catalog_index(inventory)
        crumbs = _breadcrumbs(folder)
        crumbs.append({"name": target.name, "path": relative})
        signals = _catalog_signals(inventory).get(relative, ())
        hero = bool(sidecar and sidecar.hero)
        featured = bool(sidecar and sidecar.featured)
        if hero:
            signals = (*signals, HERO_SIGNAL)
        if featured:
            signals = (*signals, FEATURED_SIGNAL)
        sourced_titles = _sourcing_index(inventory)["sourced"].get(relative.casefold(), ())
        if sourced_titles:
            signals = (*signals, sourced_signal(sourced_titles))
        signals = ordered_signals(signals)
        return {
            "sourcing_url": (
                url_for("sourcing_folder", relative_folder=folder) if sourced_titles else ""
            ),
            "hero": hero,
            "featured": featured,
            "toast": _hero_toast(),
            "version": __version__,
            "path": relative,
            "name": target.name,
            "absolute_path": str(target),
            "breadcrumbs": crumbs,
            "tree": folder_tree(index, current=folder),
            "signals": signals,
            "signal_legend": SIGNAL_LEGEND,
            "preview_size": _preview_size(target, stat.st_mtime_ns, stat.st_size),
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
            "referrers": _current_index().referring(target.name),
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

    # ---- Sourcing notes: `<folder>/sourcing/<slug>.md` and its attachments ----

    def _sourcing_index(inventory: Inventory) -> dict:
        """Every sourcing note under the catalog's folders, memoised per snapshot.

        One `is_dir` per catalog folder, and a read of each note only in the
        folders that have a `sourcing/` folder. Redone once per validation
        serial, like the hero lookup, so a note written outside the viewer
        shows up on the next refresh.
        """

        serial = cache.serial(inventory.include_vendor)
        with hero_lock:
            cached = sourcing_memo.get(inventory.include_vendor)
            if cached is not None and cached[0] is inventory and cached[1] == serial:
                return cached[2]
        folders: dict[str, tuple[list, list]] = {}
        sourced: dict[str, tuple[str, ...]] = {}
        for item in _catalog_index(inventory):
            name = item["name"]
            if name == "." or is_sourcing_path(name):
                continue
            folder = root / name
            if not sourcing_dir(folder).is_dir():
                continue
            options, problems = read_folder_options(folder, name)
            folders[name] = (options, problems)
            for option in options:
                for filename in option.for_files:
                    key = f"{name}/{filename}".casefold()
                    sourced[key] = (*sourced.get(key, ()), option.title)
        # Titles in name order, so a badge reads the same whichever note changed last.
        sourced = {key: tuple(sorted(titles, key=str.casefold)) for key, titles in sourced.items()}
        found = {"folders": folders, "sourced": sourced}
        with hero_lock:
            sourcing_memo[inventory.include_vendor] = (inventory, serial, found)
        return found

    def _forget_sourcing() -> None:
        with hero_lock:
            sourcing_memo.clear()

    def _sourcing_target(relative: str) -> tuple[Path, str] | None:
        """(folder path, workspace-relative name) for a catalog folder, or None.

        Only a folder the catalog shows may hold sourcing notes: inside the
        workspace, not the root, not itself inside a `sourcing/` folder.
        """

        target = workspace_folder(root, relative)
        if target is None:
            return None
        name = target.relative_to(root).as_posix()
        if is_sourcing_path(name):
            return None
        inventory = cache.get(include_vendor=False, hash_files=False)
        if name not in {item["name"] for item in _catalog_index(inventory)}:
            return None
        return target, name

    def _attachment_url(folder: str, name: str) -> str:
        relative = f"{folder}/sourcing/attachments/{name}"
        try:
            stat = (root / relative).stat()
        except OSError:
            return url_for("sourcing_file", relative_path=relative)
        return url_for(
            "sourcing_file",
            relative_path=relative,
            v=attachment_version(stat.st_mtime_ns, stat.st_size),
        )

    def _render_sourcing(text: str, folder: str):
        """A note's prose, rendered; its `attachments/...` links go to the guarded route."""

        def resolve(value: str) -> str | None:
            name = attachment_target(value)
            return None if name is None else _attachment_url(folder, name)

        return render_markdown(rewrite_obsidian_embeds(text), resolve=resolve)

    def _option_card(option) -> dict:
        folder = root / option.folder
        links = []
        for name in option.for_files:
            exists = (folder / name).is_file()
            links.append(
                {
                    "name": name,
                    "url": (
                        url_for("part_page", relative_path=f"{option.folder}/{name}")
                        if exists
                        else ""
                    ),
                }
            )
        return {
            "option": option,
            "anchor": f"option-{option.slug}",
            "html": _render_sourcing(option.body, option.folder),
            "for_links": links,
            "edit_url": url_for("sourcing_edit", relative_folder=option.folder, slug=option.slug),
            "folder_url": url_for("sourcing_folder", relative_folder=option.folder),
        }

    def _sourcing_shell(inventory: Inventory, current: str) -> dict:
        return {
            "version": __version__,
            "tree": folder_tree(_catalog_index(inventory), current=current),
            "form_token": app.config["FORM_TOKEN"],
            "statuses": STATUS_VALUES,
        }

    def _sourcing_crumbs(folder: str, *tail: dict) -> list[dict]:
        crumbs = _breadcrumbs(folder)
        crumbs.append(
            {
                "name": "Sourcing",
                "path": folder,
                "url": url_for("sourcing_folder", relative_folder=folder),
            }
        )
        crumbs.extend(tail)
        return crumbs

    @app.get("/sourcing")
    def sourcing_all():
        inventory = cache.get(include_vendor=False, hash_files=False)
        index = _sourcing_index(inventory)
        options = [option for items, _ in index["folders"].values() for option in items]
        problems = [problem for _, items in index["folders"].values() for problem in items]
        groups = []
        for status in STATUS_VALUES:
            members = sorted(
                (option for option in options if option.status == status),
                key=lambda option: option.folder.casefold(),
            )
            members.sort(key=lambda option: (option.date, option.mtime_ns), reverse=True)
            if members:
                groups.append({"status": status, "cards": [_option_card(o) for o in members]})
        return render_template(
            "sourcing.html",
            **_sourcing_shell(inventory, "."),
            mode="all",
            name="Sourcing",
            path=".",
            breadcrumbs=[
                {"name": "Catalog", "path": "."},
                {"name": "Sourcing", "path": ".", "url": url_for("sourcing_all")},
            ],
            groups=groups,
            cards=[],
            problems=problems,
            option_count=len(options),
            folder_count=len(index["folders"]),
            counts=status_counts(options),
            toast="",
        )

    @app.get("/sourcing/<path:relative_folder>")
    def sourcing_folder(relative_folder: str):
        found = _sourcing_target(relative_folder)
        if found is None:
            return render_template(
                "_not_found.html", version=__version__, path=relative_folder
            ), 404
        target, name = found
        inventory = cache.get(include_vendor=False, hash_files=False)
        options, problems = read_folder_options(target, name)
        saved = request.args.get("saved", "")
        toast = next((f"Saved: {option.title}" for option in options if option.slug == saved), "")
        try:
            attachments = sum(1 for item in attachments_dir(target).iterdir() if item.is_file())
        except OSError:
            attachments = 0
        return render_template(
            "sourcing.html",
            **_sourcing_shell(inventory, name),
            mode="folder",
            name=target.name,
            path=name,
            absolute_path=str(sourcing_dir(target)),
            breadcrumbs=_sourcing_crumbs(name),
            groups=[],
            cards=[_option_card(option) for option in options],
            problems=problems,
            option_count=len(options),
            attachment_count=attachments,
            counts=status_counts(options),
            toast=toast,
        )

    def _revision(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    @app.route("/sourcing/<path:relative_folder>/new", methods=["GET", "POST"])
    def sourcing_new(relative_folder: str):
        return _sourcing_editor(relative_folder, None)

    @app.route("/sourcing/<path:relative_folder>/<slug>/edit", methods=["GET", "POST"])
    def sourcing_edit(relative_folder: str, slug: str):
        return _sourcing_editor(relative_folder, slug)

    def _sourcing_editor(relative_folder: str, slug: str | None):
        """The new/edit form and its save. Writes one note; never commits."""

        if request.method == "POST":
            guard = _guard(request)
            if guard is not None:
                return guard
        found = _sourcing_target(relative_folder)
        if found is None:
            return render_template(
                "_not_found.html", version=__version__, path=relative_folder
            ), 404
        target, name = found
        path = None
        existing_text = ""
        frontmatter: dict = {}
        body = ""
        broken = ""
        if slug is not None:
            path = note_path(target, slug) if is_slug(slug) else None
            if path is None or not path.is_file():
                return render_template(
                    "_not_found.html", version=__version__, path=f"{name}/sourcing/{slug}.md"
                ), 404
            try:
                existing_text = path.read_text(encoding="utf-8")
                frontmatter, body = parse_option(existing_text)
            except (SourcingError, OSError, UnicodeDecodeError) as exc:
                broken = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
        inventory = cache.get(include_vendor=False, hash_files=False)
        cad_names = [
            record.name
            for record in inventory.records
            if (record.path.rsplit("/", 1)[0] if "/" in record.path else ".") == name
            and record.suffix.casefold() not in PROJECT_EXTENSIONS
        ]
        error = ""
        status_code = 200
        if request.method == "POST" and not broken:
            form = request.form
            wanted = dict(frontmatter)
            wanted["title"] = form.get("title", "").strip()
            for key in ("vendor", "part_number", "url", "price"):
                wanted[key] = form.get(key, "").strip()
            wanted["status"] = form.get("status", "")
            wanted["for"] = list(dict.fromkeys(item for item in form.getlist("for") if item.strip()))
            # An ISO date is stored as a YAML date; anything else hand-written
            # into the note (`2026-09`, `autumn`) is kept as the text it was.
            date_text = form.get("date", "").strip()
            try:
                wanted["date"] = datetime.strptime(date_text, "%Y-%m-%d").date()
            except ValueError:
                wanted["date"] = date_text
            body = form.get("body", "")
            frontmatter = wanted
            if not error and path is not None and form.get("revision", "") != _revision(existing_text):
                error = "the note changed on disk since this form opened; nothing was saved"
                status_code = 409
            if not error:
                written = slug
                try:
                    if path is None:
                        written = unique_slug(target, wanted["title"])
                        write_option(note_path(target, written), wanted, body, create=True)
                    else:
                        write_option(path, wanted, body, create=False)
                except SourcingError as exc:
                    error = str(exc)
                except OSError as exc:
                    error = f"could not write the sourcing note: {exc}"
                    status_code = 500
                finally:
                    _forget_sourcing()
                if not error:
                    return redirect(
                        url_for(
                            "sourcing_folder",
                            relative_folder=name,
                            saved=written,
                            _anchor=f"option-{written}",
                        )
                    )
            if status_code == 200:
                status_code = 400
        elif request.method == "POST":
            status_code = 409  # the note on disk does not parse; it is not replaced
        elif path is None:
            frontmatter = {"status": STATUS_VALUES[0], "date": datetime.now().date()}
        chosen = [str(item) for item in (frontmatter.get("for") or ()) if str(item).strip()]
        choices = [{"name": item, "present": True, "checked": item in chosen} for item in cad_names]
        choices += [
            {"name": item, "present": False, "checked": True}
            for item in chosen
            if item not in cad_names
        ]

        def value(key: str) -> str:
            item = frontmatter.get(key)
            return "" if item is None else str(item)

        crumb_name = "New option" if path is None else (value("title") or str(slug))
        return render_template(
            "sourcing_edit.html",
            **_sourcing_shell(inventory, name),
            name=target.name,
            path=name,
            absolute_path=str(sourcing_dir(target)),
            breadcrumbs=_sourcing_crumbs(name, {"name": crumb_name, "path": name}),
            creating=path is None,
            slug=slug if path is not None else "",
            note_name=f"{name}/sourcing/{slug}.md" if path is not None else "",
            broken=broken,
            raw_text=existing_text if broken else "",
            error=error,
            values={
                key: value(key)
                for key in ("title", "vendor", "part_number", "url", "price", "status", "date")
            },
            choices=choices,
            body=body,
            preview_html=_render_sourcing(body, name),
            revision=_revision(existing_text) if path is not None else "",
            option_count=len(read_folder_options(target, name)[0]),
        ), status_code

    @app.post("/sourcing/<path:relative_folder>/attach")
    def sourcing_attach(relative_folder: str):
        """Save one pasted or dropped picture or PDF; answer with its Markdown embed.

        A body larger than the cap allows is refused before it is parsed; then
        the usual localhost and token guard; then the folder, the type, the
        bytes and the size. A file is never overwritten.
        """

        if not _is_loopback(request.remote_addr):
            return Response("editing is restricted to localhost", status=403)
        length = request.content_length
        if length is None:
            return jsonify(error="the upload must state its length"), 411
        if length > MAX_ATTACHMENT_BYTES + ATTACH_ENVELOPE_BYTES:
            return jsonify(error="attachments are limited to 25 MB"), 413
        guard = _guard(request)
        if guard is not None:
            return guard
        found = _sourcing_target(relative_folder)
        if found is None:
            return jsonify(error="no such catalog folder"), 404
        target, name = found
        upload = request.files.get("file")
        if upload is None:
            return jsonify(error="no file was sent"), 400
        data = upload.stream.read(MAX_ATTACHMENT_BYTES + 1)
        if len(data) > MAX_ATTACHMENT_BYTES:
            return jsonify(error="attachments are limited to 25 MB"), 413
        try:
            saved, embed = save_attachment(
                target, upload.filename or "", data, mimetype=upload.mimetype or ""
            )
        except SourcingError as exc:
            return jsonify(error=str(exc)), 400
        except OSError as exc:
            return jsonify(error=f"could not save the attachment: {exc}"), 500
        return jsonify(
            name=saved,
            embed=embed,
            path=f"{name}/sourcing/attachments/{saved}",
            url=_attachment_url(name, saved),
        ), 201

    @app.get("/sourcing-file/<path:relative_path>")
    def sourcing_file(relative_path: str):
        """Serve one sourcing attachment, and nothing else.

        The resolved file must be inside the workspace, directly in a
        `<folder>/sourcing/attachments/` folder, with an allowed extension.
        An SVG is sandboxed by its Content-Security-Policy; nothing is sniffed.
        """

        missing = Response("no such attachment", status=404, mimetype="text/plain")
        target = workspace_file(root, relative_path)
        if target is None:
            return missing
        parts = [part.casefold() for part in target.relative_to(root).parts]
        if len(parts) < 4 or parts[-3:-1] != ["sourcing", "attachments"]:
            return missing
        suffix = target.suffix.casefold()
        if suffix not in ATTACHMENT_TYPES:
            return missing
        try:
            stat = target.stat()
        except OSError:
            return missing
        response = send_file(
            target,
            mimetype=ATTACHMENT_TYPES[suffix],
            as_attachment=False,
            download_name=target.name,
            conditional=True,
            etag=True,
            last_modified=stat.st_mtime,
            max_age=None,
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        if suffix == ".svg":
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; style-src 'unsafe-inline'; sandbox"
            )
        supplied = request.args.get("v", "")
        if (
            suffix in IMAGE_EXTENSIONS
            and supplied
            and supplied == attachment_version(stat.st_mtime_ns, stat.st_size)
        ):
            response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "private, no-cache"
        return response

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
