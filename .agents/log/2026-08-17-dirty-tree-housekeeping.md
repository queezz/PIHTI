# Dirty-tree housekeeping

**Goal:** turn the accumulated tool, CAD-curation, and folder-metadata work into
deliberate commits without blending their histories.

## Decisions

- Commit the overlapping 0.10.0–0.13.0 viewer work at its final, fully tested
  0.13.0 state. Intermediate milestones remain visible in the changelog and
  dated handoffs rather than as unverified partial source snapshots.
- Keep the reviewed CAD cleanup separate from tooling. Every deleted file was
  checked against either a current byte-identical survivor/rename or the
  different-revision consolidation ledger.
- Preserve the three human-authored Plasma Vessel folder notes exactly as
  written and commit them separately from code and CAD changes.

## Changed

- `fffddf4` — `Add assembly-first CAD repair — v0.13.0`
- `6df56ca` — `Curate reviewed CAD duplicates and component names`
- `253f8bc` — `Document plasma-vessel design intent`
- Refreshed the external `~/.venvs/pihti-dedup` environment from the declared
  `.[dev,preview,step]` extras after bootstrapping its missing `pip`.

## Verification

- `pytest`: 204 passed.
- Ruff: passed.
- JavaScript syntax check: passed.
- MkDocs strict build: passed in OS-local scratch; the existing unlisted
  `how-to-pr.md` notice and upstream Material for MkDocs 2.0 warning remain
  informational.
- `git diff --check`: passed; line-ending conversion messages only.
- Read-only duplicate inventory: 2,808 files scanned, 104 hash-duplicate
  groups, 49 renamed hash-duplicate groups, 57 same-name/same-size groups, and
  41 same-name/different-size groups.
- Deletion audit: all ElectronicsBox removals retain byte-identical current
  survivors; all three Wide Din Clip paths are exact renames; every remaining
  different-byte removal is recorded in `.agents/consolidation-ledger.jsonl`.

## Next

- Open Inventor through `PIHTI.ipj` and settle the three Wide Din Clip rename
  entries by repointing and saving their referring assemblies; the rename
  ledger intentionally remains unsettled until that evidence exists.
- The branch remains local and ahead of `origin/master`; no fetch, push, tag,
  or remote synchronization was performed.

## Usage

- Provider: OpenAI; model: Codex (GPT-5); task: dirty-tree housekeeping; child
  agents: 0; provider usage: unavailable; observed 2026-08-17 JST.
