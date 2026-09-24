# Snapshot serving and the viewer speed assessment

**Goal:** answer queezz's question "can we improve readability, speed, and
usefulness" with measurements, then fix the one thing he asked for now: the
viewer must serve from a built snapshot and refresh in the background, never
walk the disk per click.

## Decisions

- Speed root cause was a single thing: every page ran the full inventory walk
  before rendering (130 ms in isolation, 350–500 ms time-to-first-byte under
  the live server); Doctor added two more walks and Duplicates a git
  subprocess. Nothing else was slow (a warm preview image is 3 ms).
- Owner ruling 2026-09-24: build once, serve from memory, refresh in the
  background; no "preparing" waits. Implemented as `pihti-dedup` 0.14.0.
- Owner ruling 2026-09-24: do not invent metadata. No model-written
  descriptions or captions from thumbnails; folder structure is deliberate
  and queezz enters what he uses. Name *suggestions* for generic imported
  parts remain welcome as short role-based proposals he confirms.
- The mechanical implementation was dispatched to an Opus agent and the docs
  and version bump to a Sonnet agent, on queezz's live instruction; the
  orchestrating session kept the design, review, gates, and commit.

## Findings kept for the next slice (not implemented)

- The Duplicates page presents same-name/different-bytes groups such as
  `Body.ipt` as duplicates; the thumbnails show unrelated parts. That is a
  name clash for Doctor, not a duplicate. A perceptual hash of the embedded
  Inventor previews would sort the two cases cheaply.
- Generic names: 49 files in 11 folders, all vendor STEP import bundles.
  `ElectronicsBox/TempController` and `TempController-v2` share 22
  byte-identical files. Re-importing each bundle as one named part is 11
  Inventor operations, versus 49 guarded renames. Which TempController tree
  is live is queezz's call (still open).
- Metadata coverage today: 0 sidecars, 7 authored folder notes of 40
  READMEs, Inventor Description on 101 of 925 documents, Part Number
  differing from filename on 215.

## Changed

- `src/pihti_dedup/inventory.py`: `_iter_files` rewritten on `os.scandir`
  with string paths; identical records, order, and exclusions (verified
  against the persisted inventory). Walk 130 ms → 38 ms.
- `src/pihti_dedup/whereused.py`: `walk_workspace` likewise.
- `src/pihti_dedup/snapshots.py` (new): `Snapshot`, `Ticker`, `is_due`.
- `src/pihti_dedup/web.py`: `InventoryCache` gains `max_age`, `refresh`,
  `due`, `refresh_due`, `fresh=`, `on_clear`; `create_app(refresh_seconds=)`
  builds where-used, filename-location, and merged-PR snapshots plus a lazily
  started ticker; read-only views use them; the three cleanup routes now
  build plans from a fresh validation and call `cache.clear()` on success;
  the catalog folder index is memoised on inventory identity.
- `src/pihti_dedup/cli.py`: `serve --refresh-seconds` (default 5.0; 0 is the
  old validate-per-request mode, which stays the `create_app` default).
- Tests: `tests/test_snapshots.py` (new), six snapshot-mode tests in
  `tests/test_web.py`, and the `create_app` stub in `tests/test_cli.py` now
  accepts keyword arguments.
- Docs: `README.md` Duplicate-review paragraph, `.agents/CHANGELOG.md`,
  `.agents/dedup-viewer-design.md` Status; version 0.14.0 in both files.

## Verification

- pytest: 219 passed (204 existing unchanged + 15 new), fresh basetemp.
- Ruff: passed. `git diff --check`: passed (LF/CRLF notices only).
- MkDocs strict build to OS-local scratch: passed; `how-to-pr.md` unlisted
  notice unchanged.
- Test-client timings on the real workspace, warmed, median of 5:
  `/catalog` 50 → 11 ms, `/doctor` 158 → 19 ms, `/duplicates/results`
  330 → 17 ms, `/renames` 69 → 6 ms (validate-per-request vs snapshots).
- The owner's `lab pihti` instance on 4185 was not touched; it needs a
  restart to pick up 0.14.0.

## Mail

- Posted letter `20260924-119005a7-01fca8` from `cad/.` to `code/fleet`:
  make delegation to Opus/Sonnet a gate in the cold-start packet, on
  queezz's instruction. No mail was waiting for `cad/.`.

## Next

- Restart `lab pihti`; confirm pages render instantly and that a part saved
  in Inventor appears within about five seconds of browsing.
- Split name clashes out of Duplicates and collapse vendor import bundles to
  one Doctor item with a re-import instruction (UI change: route through
  fleet RULES.md §10, `WEBUI.md`, `WEBUI-COOKBOOK.md` first).
- Prepare short role-based name suggestions for the 11 vendor bundles for
  queezz to confirm.
- The four untracked `ProbeRest*` CAD files predate this session and were
  left as found.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 2 (one
  Opus implementation, one Sonnet docs); observed 2026-09-24 JST.
