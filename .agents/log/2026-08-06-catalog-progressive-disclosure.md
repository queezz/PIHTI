# Catalog progressive disclosure — pihti-dedup 0.7.0

**Date:** 2026-08-06
**Agent:** codex gpt-5
**Goal:** replace the slow, difficult-to-read all-files Catalog with a familiar
folder-first interaction that hides detail until it is requested.

## Decisions

- Use a server-rendered master/detail browser, not an accordion or virtualized
  mega-grid. The archive's real folder hierarchy supplies the information
  architecture and gives every level a durable URL and browser history entry.
- `/catalog` shows top-level systems and root files. `/catalog/<folder>` shows
  immediate child folders and files directly in that folder only. Alphabetical
  order remains useful within one level instead of acting as the whole design.
- Global search runs on the server and returns only matching files. Search and
  large leaf folders show 48 thumbnails initially and reveal 48 more only after
  an explicit request.
- Breadcrumbs and the stationary folder rail both locate the current level. The
  server opens only the active ancestry; unrelated expansions are not persisted.
- Show an authored note folded on the current folder. Keep generated indexes and
  raw editing on the dedicated `/folder/<path>` page rather than multiplying
  editors through the browse surface.

## Changed

- `src/pihti_dedup/web.py` — folder index, drill-down route, breadcrumbs,
  server-side search, bounded reveal, current-tree state, and note context.
- `templates/catalog.html` — folder cards, current-level file grid, breadcrumb,
  folded note, global search, and reveal control.
- `templates/part.html`, `templates/folder.html` — return to the relevant catalog
  folder rather than the root.
- `static/dedup.css`, `static/dedup.js` — browser layout, responsive folder cards,
  active tree state, and removal of the full-page client filter and remembered
  expansion state.
- `tests/test_web.py` — hierarchy, bounded reveal, server search, notes, and tree
  route coverage.
- `README.md`, `.agents/CHANGELOG.md`, `.agents/dedup-viewer-design.md` — 0.7.0
  behavior and rationale.

## State

- Live `/catalog`: about 956 KB and 1,218 tiles before; 56,560 bytes, 18 system
  cards, and one root file after.
- Live `/catalog/ElectronicsBox`: 12 immediate child folders and seven direct
  files, 57,435 bytes.
- Live `/catalog/3D-printing`: first 48 of 170 direct files, 69,364 bytes; asking
  for 96 produces an 89,093-byte response.
- Focused web suite: 47 passed. Full suite: 168 passed. Ruff, `git diff
  --check`, and strict MkDocs all passed.
- Visual QA used a scratch `lab` service on port 4198. Catalog landing,
  ElectronicsBox drill-down, breadcrumbs, active tree ancestry, and search were
  exercised in the in-app browser. The scratch PID and port were both verified
  gone afterwards; the owner's registered `lab pihti` service was not touched.
- No CAD file was modified.

## Next

- Use the new Catalog in ordinary review. Add a list/grid toggle only if the
  bounded thumbnail grid remains too visually dense in large leaf folders; the
  hierarchy and search should be evaluated first.
