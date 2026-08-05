# Dedup Viewer Design

## Status

The read-only first slice shipped as `pihti-dedup` 0.1.0 on 2026-08-05. The
shared scanner lives in `src/pihti_dedup/inventory.py`; the CLI and Flask viewer
consume the same classifications, and `scripts/find_duplicates.py` remains a
compatibility entry point for earlier reports.

## Purpose

Provide a local, human-in-the-loop view of filename collisions and byte-level
duplicates across the active PIHTI Inventor workspace. The viewer helps select
what to inspect in Inventor; it does not infer geometry equivalence or silently
rewrite assembly references.

## Inventor rule that drives the design

`PIHTI.ipj` defines workspace `.` and sets `UsingUniqueFilenames` to `Yes`.
Autodesk documents that, when a stored reference cannot be found, Inventor
searches the project structure for a unique file with that referenced filename.
If more than one match exists, resolution becomes ambiguous and Inventor asks the
user to choose.

Therefore the first question is not “which files share a hash?” but “which exact
filenames occur more than once inside this project?” Hashes classify the risk:

1. **Same filename, same hash** — redundant byte-identical copies. A likely
   consolidation candidate after reference review.
2. **Same filename, different hash** — an Inventor-resolution collision and the
   highest review priority. It may be a revision, resave, or unrelated geometry.
3. **Different filename, same hash** — storage duplicate/rename evidence, but not
   a filename-resolution collision.
4. **Same stem, different extension** — usually a native/drawing/export family.
   This is deliberately deferred to a related-artifacts view so it cannot be
   confused with a duplicate claim in the first slice.

Current tracked-CAD baseline, excluding `OldVersions/` and the bellows vendor
support trees: 1,259 files; 104 repeated-filename groups covering 229 files; 76
groups are byte-identical and 28 contain multiple blobs.

## Implemented first slice

### Data layer

Extract the inventory/grouping logic from `scripts/find_duplicates.py` into a
small importable module while keeping the script's CLI behavior. Records retain:

- project-relative path
- exact filename and case-folded filename key
- suffix, size, and modification time
- SHA-256
- top-level system/submission folder
- exclusion reason, when filtered from the default scope

Scanning defaults to Inventor/CAD extensions and skips `.git`, `_site`, caches,
`OldVersions`, and ignored staging. Vendor `Design Data/` and `Templates/` are a
toggleable scope, not mixed into the default engineering results.

The scan result is disposable and rebuildable. No database is needed; JSON is
appropriate for export/debugging, but generated mechanical reports should not be
committed on every scan.

### Web layer

Follow paperlib's proven shape:

- Flask, server-rendered HTML, progressive enhancement, no frontend framework.
- `GET /duplicates` returns an immediate shell with a sticky right rail.
- `GET /duplicates/results` performs or retrieves the scan asynchronously and
  returns the result fragment.
- Default bind is `127.0.0.1`; the first slice has no mutating routes.
- Client-side text and kind filters operate on the loaded groups without rescans.

Primary filters:

- filename collision / exact copy / renamed copy
- system folder or submission tree
- extension
- cross-folder only
- include vendor/package data

Each group shows its filename, classification, copy count, distinct-hash count,
sizes, and project-relative member paths. The right rail explains the kinds and
shows scan scope/statistics. An “open containing folder” action can be localhost-
only; opening the actual assembly remains an Inventor operation.

### Decisions

The first slice is report-only. A later review sidecar may record a stable group
signature, disposition (`canonical`, `keep-both`, `needs-inventor`, `package-
baggage`), canonical path, reviewer, date, and note. Recording a decision must not
move CAD.

Before any web mutation ships:

- add a CLI twin
- preview the complete operation
- verify Inventor references or record the verification gap
- move to recoverable quarantine rather than delete
- re-scan and open affected top-level assemblies in Inventor

## What cannot be inferred automatically

- Different hashes do not prove different geometry.
- Identical exported STL/STEP files do not prove their native Inventor sources
  are interchangeable.
- A filename match does not reveal which assembly currently references which
  path.
- Inventor resaves can change bytes without a meaningful design change.

Reference evidence remains a second phase. The practical first step is to link a
collision group to an Inventor/Design Assistant “where used” check and record the
human result. Direct automation through Inventor APIs is optional later and must
not block the useful read-only viewer.

## Sources and precedents

- paperlib `src/paperlib/webapp.py`: server-rendered shell, sticky rail, async
  `/duplicates/results`, local/read-only boundaries.
- paperlib `src/paperlib/library.py`: signal grouping followed by stronger
  fingerprint classification.
- Autodesk Inventor Help, “To Work with Projects”:
  https://help.autodesk.com/cloudhelp/2025/ENU/Inventor-Help/files/GUID-34126F60-3093-4144-8AA5-809B4D35DCA1.htm
- Autodesk Inventor Help, “About Resolution of File Search”:
  https://help.autodesk.com/cloudhelp/2022/ENU/Inventor-Help/files/GUID-CD73F9CD-F485-4CAE-AA64-0E80BA15CCA3.htm
- Autodesk Inventor Help, “Pack and Go Reference”:
  https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Help/files/GUID-B25088E2-AF91-4774-A168-C141F6147AD8.htm
