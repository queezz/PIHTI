# One layout on every page, Doctor rows that fix through Inventor (pihti-dedup 0.27.0)

**Goal:** two deliverables from the orchestrator's brief. A: move every page
onto the catalog's shell (context rail left, page centre, navigation rail
right, both pinned), keep the catalog pixel-identical, cut copy to punch
lines. B: give Doctor the button the rename repair already had: repoint a
missing name to a chosen file through Inventor, and rename a repeated name
with the repair, all recorded in the rename ledger. Two owner amendments came
in mid-task: drop the part page's "Part Number differs from the filename"
callout, and move the part page's Rename into the left rail as a compact card.

## Decisions

- Shell: `.work-grid.two-rail` replaces the `.catalog-grid` rules
  (`25.5rem minmax(0, 1fr) 17rem`, `.two-rail > .work-main | .rail-context |
  .rail-tree`); the catalog, part and sourcing pages keep `catalog-grid` beside
  it. The left rail keeps its exact catalog height; the right rail takes the
  tree card's ceiling. Both scroll inside themselves only when a page puts
  more there (Duplicates' folder list at 1000px: 966 in 843). The scrolling
  test now lists the two rails before the inspector facts and the tree.
- `_shell.html`: `page_bar` (the catalog bar's look, in the flow, crumbs plus
  the page's one filter), `session_card`, `jump_card`, and `fix_row`. The
  Renames filter was a sticky `.filterbar` sliding over the first card; the
  bar now scrolls away with the page.
- Per page as briefed. Renames: Ledger chips and a two-line note left, Kind
  chips (rename / move, a visit-only filter in dedup.js, null-checked) plus
  Will prompt / Repaired right, cards left-aligned at 70rem. Duplicates: Scan,
  Merge cleanup, Merged PRs left; Groups (with the type select and the
  cross-folder box moved out of the filter bar), Folders right. Doctor pages:
  facts and the Inventor card left, jump lists right, breadcrumbs instead of
  "All doctor queues" buttons. STEP mirror: Mirror and the 0.26.0 Inventor
  card (hooks and data attributes unchanged) left, On this page right, a
  "STEP mirror" top-bar tab current on its three routes, the meta count kept.
  Removed, the consolidated-path answer, Sourcing, part and folder pages on
  the same shell. Doctor panels capped at 60rem (at 2560px a queue row spread
  name and chip 1450px apart; now 958px).
- Copy: explanatory paragraphs cut everywhere touched; kept sentences only in
  destructive confirmations (the rename confirm, the consolidation confirm in
  dedup.js, the collision warning). Coloured edge bars removed (Duplicates,
  Removed, Renames, assembly problems, warnings). 84 dead CSS rules for the
  old Doctor, workbench and catalog-heading markup removed.
- Doctor queue: one line per item under Interrupted saves (moved first: a
  leftover may hold newer work), Missing file, Ambiguous filenames
  (`#name-clashes` kept for Duplicates' pointer), Generic names, Assemblies,
  Standard parts. Headlines are the section titles rather than repeated on
  every row. Missing file = old name of an open ledger rename, no file,
  still named: the mirror's needs-Doctor rule, so byte-scan fossils stay off.
- Repoint: `POST /doctor/name/<name>/repoint` (token, loopback; `referrer`,
  `target`, `origin` name | assembly | doctor, `assembly`). Revalidates, then
  `repair_references(session, [referrer], name, target, rename=lambda: None)`.
  On `repaired`, `renames.record_repoint`: repaired in the entry that renamed
  the name to the chosen file, not applicable in the name's other entries
  listing that referrer, settled (will_prompt false) once complete; otherwise
  a new settled line with note "repointed through Inventor; no file was
  renamed". No confirmation step (reversible). Failures land on the row and
  record nothing; a refusal for an assembly without a row is the page's error
  line. Candidates: ledger successors first, then same-type files whose stem
  starts with the old stem; preselected only when exactly one sits in the
  assembly's folder or only one exists, otherwise "Choose file" is required.
  The queue fixes in place for one assembly and one candidate with a session.
- Rename and fix: the existing Doctor rename with `repair=1` behind a new row
  per copy: `suggest_unique_name` pre-fills the box (`RKC CONTROLLER v2.ipt`
  for `TempController-v2`, `RKC CONTROLLER Temp.ipt` for `TempController`;
  never an existing or already-suggested name). No session: plain **Rename**
  (manual repointing, as before) and the "Start Inventor…" card.
- Coordinator follow-up: no dialog is ever left to the owner. The repoint
  opens the referrer (and reopens it to verify) with
  `Documents.OpenWithOptions(path, options, False)`, `options` a
  `TransientObjects.CreateNameValueMap()` with `SkipAllUnresolvedFiles` True,
  so Resolve Link never shows; the missing descriptor is replaced as before.
  `repair_references(..., skip_unresolved=True)` does this only for Doctor's
  missing-name path; a rename keeps plain `Open`. A session without that API
  gets "Inventor would ask" and no plain `Open` fallback. SilentOperation is
  never set. The fake learned `TransientObjects.CreateNameValueMap`,
  `OpenWithOptions` (logged with its options) and `legacy_api`.
- Coordinator follow-up: the queue's Assemblies section lists only
  assemblies with an actual problem (generic, carried twice, or a missing
  name an open rename left behind, each name counted once): 37 rows on this
  tree instead of 258. The STEP mirror's needs-Doctor rule was not changed.
- Part page: Rename card in the left rail (same fields and route, the repair
  checkbox as before, one `copy-path` chip, no paragraph; the confirmation
  keeps its lists); File card actions became chips; the mismatch callout and
  its CSS removed, the Part number fact row stays.

## Changed paths

- `src/pihti_dedup/inventor_session.py`: `repair_references(...,
  skip_unresolved=)`, `_open_skipping_unresolved`, `WOULD_ASK`.
- `src/pihti_dedup/renames.py`: `record_repoint`, `REPOINT_NOTE`,
  `suggest_unique_name`, `_rewrite_ledger`.
- `src/pihti_dedup/web.py`: `_session_card`, `_repoint_candidates`,
  `_fix_rows`, `_fixed_note`, `_doctor_queue_context`,
  `_doctor_assembly_context`, `doctor_repoint`, `DOCTOR_ABSENT`, `_fix_words`,
  name-page context (suggestions, fix rows), folder context (tree), renames
  (move count), standard-parts group lines cut, part-number mismatch removed.
- Templates: new `_shell.html`; `base.html`, `catalog.html`, `part.html`,
  `folder.html`, `sourcing.html`, `sourcing_edit.html`, `renames.html`,
  `duplicates.html`, `_results.html`, `doctor.html`, `doctor_name.html`,
  `doctor_assembly.html`, `doctor_standard_parts.html`, `_repair_confirm.html`,
  `removed.html`, `removed_path.html`, `step_mirror.html`.
- `src/pihti_dedup/static/dedup.css`, `static/dedup.js` (Kind filter).
- Tests: new `tests/test_doctor_fix.py` (23); `tests/inventor_fake.py`
  (dialog-free open); updated `test_web.py`,
  `test_inventor_repair_flow.py`, `test_standard_parts.py`,
  `test_step_mirror.py`.
- `pyproject.toml`, `src/pihti_dedup/__init__.py` (0.27.0), `README.md`,
  `.agents/CHANGELOG.md`, `.agents/dedup-viewer-design.md`.

## Verification

- Gates: pytest 477 passed (fresh basetemp); ruff clean; `node --check` on
  both scripts; `git diff --check` clean; strict MkDocs build clean.
- Scratch viewers, never the live 4185: 48191 on the real tree with
  `session_factory=lambda: None`, 48192 on a scratch Wide Din Clip / RKC
  workspace with the fake Inventor from `tests/inventor_fake.py`, 48193 on
  HEAD's `src` (git archive) for the catalog comparison; scratch cache and
  mirror folders; `--refresh-seconds 0`; process trees killed, ports free.
- Browser pane at 1600×1000 (read_page / JS, screenshots are small): on every
  page (catalog, folder, part, sourcing, sourcing editor, duplicates, doctor,
  name, assembly, standard parts, renames, removed, consolidated path, STEP
  mirror, folder note) the left rail is x 24 w 408, the main column x 450 w
  821, the right rail x 1289 w 272, both rails `sticky 84px`, order |+|, no
  horizontal overflow. Catalog against 0.26.0: identical rects for the bar,
  the three left cards, legend, tree card, folder cards and tiles. Renames:
  the bar is static; at scroll 0/60/200 the first card's top is never covered
  (elementFromPoint), card left-aligned at x 450. Fold at 1150: rails static
  in one right column, fix-row form under the name. 2560: renames card capped
  at 1120px left-aligned, doctor rows 958px on one line.
- Fake Inventor end to end: Fix in Inventor on TempController.iam repointed it
  to Wide Din Clip V1.ipt (ledger: repaired in V1, not applicable in v2 and
  v3, none settled); Rename and fix on RKC CONTROLLER (TempController-v2) showed
  the confirm (saves TempController-v2.iam, TempController.iam uses the other
  copy), then renamed and settled. Renames Kind chips 12 → 6 / 6 → 12;
  Duplicates type and cross-folder filters work from the right rail.

## Needs the owner with a real Inventor

- Fix in Inventor on the real Wide Din Clip referrers (TempController.iam,
  TempController-v2.iam, cosel-psu-din-clip.iam): that `OpenWithOptions` with
  `SkipAllUnresolvedFiles` opens them with no dialog through comtypes (the
  NameValueMap `Add` takes a Python bool as its VARIANT), that the skipped
  reference is listed with `ReferenceMissing` and `ReplaceReference` repoints
  it, and the verify-on-reopen result; then that the three ledger entries
  settle and the assemblies leave the mirror's Needs Doctor list.
- Rename and fix on a real repeated name (the `board.ipt` bundles or RKC
  CONTROLLER): the confirmation's per-assembly resolution and the save.
- His eye on the layout at his widths.

## Usage

- Provider: Anthropic; implementation agent: Claude Opus 5.5; observed
  2026-09-25 JST.
