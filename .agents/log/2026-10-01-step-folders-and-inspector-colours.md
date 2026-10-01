# STEP folders and inspector colours — 2026-10-01

## Goal and decisions

queezz reported the workspace-wide file dropdown unusable and asked for folder
navigation/search, a catalog edit entrance, and colours in the usual inspector.
Ship these corrections as pihti-dedup 0.30.1, preserving the catalog shell.
Precedents: the existing catalog folder navigation, inspector action row and
STEP viewer rails. Read Fleet UI law and cookbook; proved browser DOM access
before implementation.

## Changed

- STEP selector now starts with files directly in the current folder, with
  breadcrumb buttons, expandable child folders, scoped name/path search and
  an explicit all-folder search. Folder and search scope survive reload.
- Catalog file and hero tiles carry a direct edit URL; the inspector offers
  Edit in STEP viewer. The editor names the loaded file independently of search.
- Shared 3D loader uses the STEP editor's named-occurrence reader and mapping
  for original and saved colours. Cached coloured meshes key source digest and
  map revision. Geometry-only previews remain the optional-dependency fallback.
  Normals are derived when the browser needs them. Still thumbnails are unchanged.
- Version pair, changelog, README, route assertions and viewer size budget updated.
  The source-length guard was raised to include appearance loading; no framework
  or external asset dependency was introduced.

## Verification

- Full suite: 502 passed in 57.16 seconds. Initial run: 501 passed, one source-
  length budget failure; adjusted that guard for the added capability.
- Focused simulation tests passed, including catalog entrance and saved-colour
  ranges. Ruff, three JavaScript syntax checks and diff check passed.
- Strict MkDocs build passed to external scratch.
- Isolated Lab step-test with 1,000 synthetic STEP files: root file list remains
  scoped; search returns ten matching files, cross-folder search and reload work.
- Browser checked catalog edit entrance, saved cream/blue inspector colours,
  enlarged view, part-page 3D canvas, isolate/fit/up axis/search and Escape reset.
- Perimeter: top tabs, Back/Forward, STEP mirror links and deep-link reload;
  no new anchors. At 1400x1000 and 1400x700 both rails stay at top 84px, left
  24px/1088.67px, widths 408px/272px; page scroll range zero. Existing rail
  scrolling accommodates the selector. No console errors observed.
- Used synthetic workspace only; no real CAD or simulation assignments changed.

## Cleanup and next

Reused the prior machine-local STEP verification scratch; retained for fixtures,
exports and browser evidence. Scratch Lab launcher PID 36912, listener 37512,
port 48943: identity checked, lab stop killed the tree, processes and listener
absent afterwards. Owner service was untouched. Test browser closed and viewport
override reset. Restart the ordinary lab pihti service to load cached templates.

## Usage receipt

Provider OpenAI; model GPT-6; task STEP navigation and colours; child agents 0.
Provider usage unavailable. Worked directly on this cohesive UI correction.
