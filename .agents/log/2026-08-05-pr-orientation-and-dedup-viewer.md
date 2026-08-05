# Orient merged PRs and build the dedup viewer

**Date:** 2026-08-05
**Goal:** Update the stale checkout, characterize all merged student PRs, and
deliver a safe local duplicate-review viewer.

## Decisions

- Treat exact filename as the primary Inventor risk signal because `PIHTI.ipj`
  uses workspace `.` with unique filenames enabled.
- Use hashes to classify filename groups, never to infer geometry equivalence.
- Adapt paperlib's Flask shell, asynchronous results, filters, and sticky rail;
  keep PIHTI's first slice read-only.
- Establish the fleet-canonical PIHTI docs surface without adding application
  packaging or claiming a Python environment exists.
- Leave the legacy flat June handoffs where they are; put new handoffs in
  `.agents/log/`.
- Use Flask rather than FastAPI: this is a filesystem-first, database-free local
  view, matching paperlib rather than the database-backed archive applications.
- Use `~/.venvs/pihti-dedup`; the shorter `~/.venvs/pihti` already belongs to the
  separate pihtivacuum project and was not modified.
- Make `lab pihti` the normal launch surface; the direct Python command is a
  development fallback, not the user-facing handoff.

## Evidence

- Checkout fast-forwarded cleanly from `cb38f1e` to PR #3 merge `2e29170`.
- PR #1: 123 added, 4 modified; 42 exact pre-existing copies, all under
  `Plasma Vessel_2026/`; 9 same-name/different-content additions.
- PR #2: 1,278 added files / 60.36 MB. `Design Data/` plus `Templates/` account
  for 1,263 files and about 95% of bytes; only 15 files are at `bellows/` root.
  The package contains 67 exact-duplicate groups covering 166 files.
- PR #3: 34 added, 14 modified, no deletions in the actual merge. Two exact
  component pairs now exist across `BoronProbe_2026/parts/` and
  `Plasma Vessel_2026/contents/`: `B_probe_bearing.ipt` and
  `B_probe_bearing_without_holes.ipt`.
- Current CAD baseline (excluding `OldVersions` and bellows vendor support):
  1,259 files, 104 repeated-filename groups, 76 exact-only groups, 28 variant
  groups.

## Changed

- `AGENTS.md` — PIHTI environment, read order, invariants, gates, and handoffs.
- `.agents/REPOSITORY_MAP.md` — project boundaries and folder roles.
- `.agents/directions.md` — open dedup, submission-curation, and docs work.
- `.agents/CHANGELOG.md` — dated shipped milestones.
- `.agents/dedup-viewer-design.md` — viewer architecture and safety boundary.
- `.agents/README.md` — canonical read order and layout.
- `.agents/log/2026-08-05-pr-orientation-and-dedup-viewer.md` — this handoff.
- `pyproject.toml`, `src/pihti_dedup/` — installable scanner, CLI, Flask viewer,
  templates, and static UI at tool version 0.1.0.
- `scripts/find_duplicates.py` — compatibility entry point over the shared core.
- `tests/` — focused classification, exclusions, compatibility, route, and
  version tests.
- `README.md`, `AGENTS.md`, `.gitignore` — user commands, exact environment and
  gates, and Python cache exclusions.
- Sibling `20-Code/lab-cli` — registered the optional `pihti` service against a
  logical `drawings` root, documented it, and bumped the launcher to 0.10.5.

## State

- No CAD file was moved, renamed, deleted, or rewritten; every route remains
  read-only.
- External environment `~/.venvs/pihti-dedup` is installed editable with dev
  dependencies. The existing `~/.venvs/pihti` environment was left untouched.
- Gates: 12 tests pass; Ruff and `git diff --check` pass.
- The real scan reproduces the baseline: 1,259 files, 104 repeated-filename
  groups, 28 collisions, 76 same-name exact groups, plus 9 renamed-copy groups.
- Browser validation loaded 113 cards with no console errors; collision filtering,
  Pack-and-Go scope switching, and stationary filter/rail behavior worked.
- `lab help pihti` resolves the PIHTI checkout and `pihti-dedup` venv; lab-cli's
  179 tests and doctor gate pass. This machine's private config now maps the
  logical `drawings` root without putting an absolute path in the registry.
- `master` matched `origin/master` before this session's documentation and tool
  edits.

## Next

- Use the viewer to characterize the 28 same-name/different-hash collisions and
  identify which need Inventor “where used” review first.
- Decide whether to add a review sidecar and related-artifact view.
- Separately open the bellows assemblies in Inventor and identify the primary one
  before planning removal of Pack-and-Go baggage.
