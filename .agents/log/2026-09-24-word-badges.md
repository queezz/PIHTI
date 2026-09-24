# Word badges replace dots (pihti-dedup 0.19.2)

**Goal:** queezz, 2026-09-24: "matching legend to the signals is hard... fleet
relies on badges with a tag in a colored box. That is self explaining."

## Decisions

- Every tile mark is a lowercase word in a small tinted box, fleet's chip
  shape and tints, in a row under the tile's size line: `clash`, `copy`,
  `renamed`, `unhashed`, `generic` (outline), `newer`, `main`, `featured`.
  The inspector, the part page's File card and the Legend use the same badge
  macro; the Legend keeps the long meaning beside each badge and stays
  bottom-anchored at a constant height.
- Tiles and main-assembly cards use CSS subgrid so a wrapped badge row keeps
  the whole grid row aligned (Chromium 117+ / Firefox 71+; desktop only by
  owner decision, so acceptable).
- Measured inspector/legend tops: 440/769 px at 1920×1000, 344/469 px at
  1920×700, identical on root, folder, search and part pages at every scroll
  depth.
- Implementation by an Opus agent; review, gates and commit here.

## Changed

- `src/pihti_dedup/web.py`, templates `_file_tile.html` (badge macro),
  `part.html`, `catalog.html`; `dedup.css`, `dedup.js`; `tests/test_web.py`
  (8 updated, 1 added); version 0.19.2, CHANGELOG, design doc, README
  tile-marks paragraph.

## Verification

- pytest 286 passed, fresh basetemp; ruff clean; `node --check` clean;
  `git diff --check` clean; strict MkDocs build clean. Perimeter Walk on a
  scratch copy (port 48993, stopped and port-checked): 297 links and images
  200; filter, inspector toggles, Back/Forward behave; folds at 1150.
- Left uncommitted on purpose: the owner's own Inventor save of
  `bellows/bellows.iam` and his untracked sidecars.

## Loose ends

- At 700 px tall the inspector has room for name and toggles only; the tile
  badges carry the marks there. A part page with four or more marks would
  push the legend at that height.

## Next

- Sourcing notes with pictures and PDFs per folder, following pihti-log's
  paste-and-attach precedent (owner request 2026-09-24).

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1 (Opus
  implementation); observed 2026-09-24 JST.
