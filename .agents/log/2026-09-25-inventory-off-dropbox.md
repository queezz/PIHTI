# The persisted inventory leaves Dropbox (pihti-dedup 0.27.2)

**Goal:** stop Dropbox conflicted copies of the viewer's inventory. The viewer
now runs on two machines against the one synced workspace; both wrote
`.pihti-dedup/inventory-default-v1.json`, and Dropbox kept
`inventory-default-v1 (powerq's conflicted copy 2026-09-25).json`. The
inventory is a rebuildable cache, so it belongs in the machine-local cache
root with previews and meshes (0.23.1). Also closes the directions item
"Git-history previews still cache inside the workspace".

## Decisions

- `InventoryCache` persists every scope in `cache_root(workspace)/inventory/`
  (`inventory-default-v1.json`, `inventory-vendor-v1.json`; the name is
  `inventory-<scope>-v<SCHEMA_VERSION>`). The viewer has only these two
  scopes; staging is not an `InventoryCache` scope. `create_app` passes the
  folder from the root it already resolved (`store=`); a bare
  `InventoryCache` resolves `cache_root` on first use and, if the root is
  refused, simply does not persist.
- Warm start: when the machine-local file for a scope is absent, `_load`
  reads the old `.pihti-dedup/` copy once per scope per process. It passes
  the same schema and scope checks and only serves as the `previous`
  snapshot, so a digest is reused only where path, size, and mtime still
  match the disk. A scope counts as persisted only after it was loaded from,
  or written to, the machine-local file; `_validate` stores an unpersisted
  scope even when nothing changed, so the first validation after a warm start
  writes the new file and the old copy is never read again. The old file is
  never written, renamed, or deleted.
- Git-history previews (`/doctor/history-preview/...`) now cache in
  `cache_root(workspace)/git-previews/`.
- Quarantine: left where it is. New runs already go to the sibling
  `<workspace>-quarantine/runs/` (in Dropbox, shared: content, not cache);
  runs under `.pihti-dedup/quarantine/` stay listed and restorable. After
  this change nothing writes `.pihti-dedup/`. The rename ledger is in
  `.agents/` and was not touched. The scanners still skip `.pihti-dedup/`.
- Readers: only the viewer ever read or wrote the persisted inventory. The
  CLI `scan`, `merge-cleanup`, and `warm-previews` walk the disk themselves,
  and no `--json` output named the file, so those commands needed no change.
  The Doctor and Duplicates pages read through the shared `InventoryCache`.
- `serve` and `create_app` now print/log the root as `machine-local cache:`
  (was `preview and mesh cache:`), since it holds four caches.
- README's merge-cleanup paragraph still said `.pihti-dedup/quarantine/`;
  corrected to the sibling store.

## Changed paths

- `src/pihti_dedup/web.py` — `INVENTORY_DIRNAME`, `GIT_PREVIEWS_DIRNAME`,
  `LEGACY_DIRNAME`; `InventoryCache` store folder, `_load`/`_read` split with
  the one-time warm start, `_persisted` rule in `_validate`/`_store`;
  history-preview store; log line.
- `src/pihti_dedup/cli.py` — `serve` cache line.
- `src/pihti_dedup/cache_root.py` — module docstring lists the four folders.
- `tests/test_web.py` — inventory in the cache root, both scopes land there,
  warm start once then ignored (a digest planted in the old copy is never
  adopted), the old copy tried once per scope and invalid JSON ignored,
  Git-history preview in the cache root with no `.pihti-dedup/` after a
  Doctor visit; log-line wording.
- `tests/test_cli.py` — `serve` line wording.
- `README.md`, `AGENTS.md`, `.agents/dedup-viewer-design.md`,
  `.agents/directions.md` (item removed), `.agents/CHANGELOG.md`.
- `pyproject.toml`, `src/pihti_dedup/__init__.py` — 0.27.2.

## Verification

- `pytest -q -p no:cacheprovider --basetemp ...` — 488 passed.
- `ruff check src tests scripts/find_duplicates.py` — clean.
- `git diff --check` — clean.
- `mkdocs build --strict` into a temp folder — clean.
- No live viewer, no Inventor, no owner cache touched; all tests use tmp
  workspaces and the per-test `PIHTI_DEDUP_CACHE_ROOT`.

## Next steps

- Restart `lab pihti` on each machine: the first start warms from the old
  JSON and writes `%LOCALAPPDATA%\pihti-dedup\PIHTI-<12hex>\inventory\`.
- Then the owner deletes `.pihti-dedup/inventory-*.json`, any conflicted
  copies, `.pihti-dedup/git-previews/`, and the pre-0.23.1
  `.pihti-dedup/previews/`. Not committed.
