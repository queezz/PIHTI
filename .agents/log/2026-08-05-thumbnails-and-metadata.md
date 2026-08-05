# Thumbnails and metadata sidecars — pihti-dedup 0.3.0

Date: 2026-08-05
Agent: opus

## Goal

"I need thumbnails and the metadata helper." Make the review surface visual, and
give every CAD file a place to record intent that is not the CAD file itself.

## What shipped

- `src/pihti_dedup/inventor_meta.py` — a self-contained MS-OLEPS reader for
  `.ipt`/`.iam`/`.idw`/`.ipn`. Extracts flattened iProperties, user-defined
  properties, and the embedded preview image. Depends on `olefile` only: no
  Inventor, no COM, no Windows API.
- Thumbnails everywhere: `GET /preview/<repo-relative-path>` serves the embedded
  image; every duplicate member row, the new catalog, and the part page use it.
- `GET /catalog` — per-folder thumbnail grid over the existing scanner's file
  list, with a client-side text filter and a folder rail.
- `GET /part/<repo-relative-path>` — preview, iProperties, file facts, and the
  sidecar editor.
- Metadata sidecars: `<cad filename>.md` with YAML frontmatter plus prose.
  Created seeded from iProperties from the part page, edited raw in a textarea,
  or bulk-seeded with `pihti-dedup meta seed --dry|--apply`.
- Runtime deps `olefile>=0.47` and `pyyaml>=6.0`; version 0.2.0 → 0.3.0 in
  `pyproject.toml` and `src/pihti_dedup/__init__.py`.

## Decisions

- **Sidecar naming is the full filename plus `.md`**, not the stem. A part and
  its drawing share a stem (`B_probe_bearing.ipt` / `.idw`); stem-based naming
  would silently merge two files' notes into one. `B_probe_bearing.ipt.md` also
  sorts next to its file and survives a copy.
- **Match property sets by FMTID, never by stream name.** Inventor writes them
  under scrambled names. PID 255 repeats each set's own name and is the fallback
  for an FMTID the table has not seen.
- **Withhold mass properties unless `Valid MassProps` (PID 62) vouches for
  them.** They are a cached snapshot Inventor invalidates. This workspace only
  ever shows 1, 17, or 31 — never 0 — so the individual bits stay undocumented
  and a missing or zero flag means "report nothing". Values are also frequently
  absent under a valid flag (660 of 699 parts have density but no mass), so
  presence is checked per field.
- **No auto-commit.** Sidecar writes reuse the loopback-plus-token boundary of
  the existing delete action and validate that the frontmatter parses before
  touching disk. A sidecar then just appears as an untracked or modified file in
  the owner's own Git flow.
- **Bulk seeding covers Inventor documents only.** `.stl`/`.stp`/`.dwg` carry no
  iProperties, so an automatic sidecar for them would be empty ceremony. The web
  button still works on any scanned file.
- Previews are read, never rendered. Files without an embedded preview get a
  neutral inline SVG placeholder instead of a broken image.

## Evidence

Measured across the 999 Inventor documents in the workspace:

- 996 carry a PNG preview. The three without one are STEP imports under
  `ElectronicsBox/esp32-ambient-logger/STEPs/`.
- 227 have a Part Number that differs from their filename stem — the mismatch
  the part page now surfaces.
- `Mass == Volume * Density` held exactly on every part carrying all three,
  which is what confirms PIDs 58/60/61.
- Reading one document costs ~3–25 ms; `/catalog` renders 1,218 tiles across 99
  folders in ~0.7 s, and previews are cached by path and modification time.

## Verified

- `pytest -q` — 57 passed (was 39): OLEPS parsing against synthetic property-set
  blobs, sidecar round-trip and refusal cases, preview/catalog/part route smoke
  tests including traversal rejection and the token guard.
- `ruff check src tests scripts/find_duplicates.py` — clean.
- `git diff --check` — clean.
- Flask test client only; no live server was started.
- Path containment checked by hand against `../`, `..%2F`, `C:\Windows\win.ini`,
  and `/etc/passwd`; all refused.

## Next

- Show a sidecar's status and tags on duplicate rows and catalog tiles.
- The per-group *review disposition* record is still open; this chunk shipped
  the per-file metadata sidecar, which is a different thing.
- Quarantine still defaults to `.pihti-dedup/` inside the workspace. The store
  was relocated to `../PIHTI-quarantine/` by hand on 2026-08-05; the default is
  now recorded in `directions.md`.
- No sidecars were seeded in the real workspace. `meta seed --apply` would
  create ~999 files; that is the owner's call, not an agent's.
