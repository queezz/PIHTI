# Dedup Viewer Design

## Status

The read-only first slice shipped as `pihti-dedup` 0.1.0 on 2026-08-05. Version
0.1.1 corrected the working shell against the fleet/Paperlib precedent and added
local merged-PR and folder analysis. Version 0.2.0 split the context across two
stationary rails and added preview-first, recoverable cleanup for exact copies
introduced by a merge. The shared scanner lives in
`src/pihti_dedup/inventory.py`; the CLI and Flask viewer consume the same
classifications, and `scripts/find_duplicates.py` remains a compatibility entry
point for earlier reports.

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

Follow paperlib's proven shape, specifically its Duplicates screen and
`.folder-grid` / `.folder-panel` working shell:

- Flask, server-rendered HTML, progressive enhancement, no frontend framework.
- `GET /duplicates` returns an immediate shell whose top bar names the view; do
  not repeat that identity with a large page heading or introductory block.
- `GET /duplicates/results` performs or retrieves the scan asynchronously and
  returns the result fragment.
- The result fragment begins with one shared three-column grid: results plus two
  fixed-width rails. Both rails start at their sticky offset, never move when the
  page scrolls, and never get an internal scrollbar. On narrower screens they
  stack after the results.
- Default bind is `127.0.0.1`. Actual cleanup is localhost-only; the remaining
  routes are read-only.
- Client-side text and kind filters operate on the loaded groups without rescans.
- Follow Paperlib's `pl-dup-filter` decision: persist the complete working review
  context in local storage and reapply it after every async fragment replacement.
  PIHTI includes text, kind, folder, merged PR, extension, cross-folder, and
  vendor scope rather than only Paperlib's kind and text.
- Colored group counts in the rail are buttons because they filter. Group state
  inside result cards is plain text/icon metadata, not button-like pills.
- Every member row has its own copy-path action. There is no group-level bulk
  copy because the Inventor review proceeds one path at a time.
- Member paths are rendered and copied with Windows separators. Rows show the
  local modified time as evidence alongside size and a short hash.
- A cleanup/rescan keeps the old list visible but dimmed while the fresh scan is
  fetched. It restores an unaffected visible group to the same viewport offset,
  moves keyboard focus to that group's next action after a deletion, and uses a
  fixed toast for success. Do not prepend a notice or replace the working list
  with a spinner during a mutation; both cause avoidable spatial resets.

Primary filters:

- filename collision / exact copy / renamed copy
- project folder
- recent merged PR, derived from local first-parent Git history
- extension
- cross-folder only
- include vendor/package data

Each group shows its filename, classification, copy count, distinct-hash count,
sizes, modified times, and project-relative member paths. The two right rails
hold actionable kind, folder, and merged-PR selectors plus compact scan
statistics. Zero-result folders and PRs remain visible because absence of
duplicate evidence is itself useful after a merge. An “open containing folder”
action can be localhost-only; opening the actual assembly remains an Inventor
operation.

### Merged-PR cleanup

`merge-cleanup --pr N --dry` and the web preview share one planner. Candidates
must be same-name, byte-identical files added by that merge, with at least one
current identical survivor outside the merge. Modified paths, renamed-only hash
matches, and groups whose every copy came from the merge are protected.

Actual execution requires `--apply --references-checked` or the equivalent
localhost-only, token-protected web confirmation. It re-scans, compares the dry
plan signature, verifies every candidate's path, size, modified time, and SHA-256, then moves
files to `.pihti-dedup/quarantine/<timestamp>-pr-N/`. A JSON manifest records
original paths, surviving copies, hashes, and the required post-apply Inventor
assembly check. A mid-operation failure rolls moved files back.

### Individual exact-copy cleanup and `newVer`

Every member of an exact or renamed exact-byte group may be explicitly selected
with **Delete**. The confirmation names that Windows path and at least one
byte-identical survivor. The localhost/token-protected endpoint force-rescans,
compares a signature covering path, size, modified time, and SHA-256, and moves
the one selected member to recoverable quarantine with its own manifest.
Different-byte collisions never receive this action.

Seven current renamed-copy groups match `name.ipt` plus `name.newVer.ipt`. In
all seven, the two files have identical SHA-256 values and identical filesystem
modified timestamps. The UI characterizes these as **newVer pairs** but says
“origin unproven”: neither the bytes nor the timestamp establishes that Autodesk
Inventor created the suffix, and no Autodesk documentation for it was found.

### Decisions

The 0.1 first slice was report-only. Version 0.2 adds guarded merged-PR and
individually confirmed exact-byte quarantine operations. A later review sidecar may record a stable group
signature, disposition (`canonical`, `keep-both`, `needs-inventor`, `package-
baggage`), canonical path, reviewer, date, and note. Recording a decision must not
move CAD.

Before any broader web mutation ships:

- retain a CLI twin
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

- fleet `RULES.md` section 10: stationary navigation rail, shared grid, rail-card
  vocabulary, and Paperlib-before-new-UI rule.
- paperlib `src/paperlib/webapp.py` `_DUPLICATES` screen and `.folder-grid` /
  `.folder-panel` CSS: server-rendered shell, rail aligned at its sticky top from
  initial paint, async `/duplicates/results`, real filter buttons, and local
  read-only boundaries. Attendance-style dashboard headers are not a precedent
  for this viewer.
- lecturedeck `STYLE_GUIDE.md`: accents communicate semantic emphasis and are not
  decoration applied to every object.
- paperlib `src/paperlib/library.py`: signal grouping followed by stronger
  fingerprint classification.
- Autodesk Inventor Help, “To Work with Projects”:
  https://help.autodesk.com/cloudhelp/2025/ENU/Inventor-Help/files/GUID-34126F60-3093-4144-8AA5-809B4D35DCA1.htm
- Autodesk Inventor Help, “About Resolution of File Search”:
  https://help.autodesk.com/cloudhelp/2022/ENU/Inventor-Help/files/GUID-CD73F9CD-F485-4CAE-AA64-0E80BA15CCA3.htm
- Autodesk Inventor Help, “Pack and Go Reference”:
  https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Help/files/GUID-B25088E2-AF91-4774-A168-C141F6147AD8.htm
