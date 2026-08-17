# Reviewed collision consolidation — pihti-dedup 0.11.0

**Goal:** let queezz keep one manually compared collision member, recoverably
remove the others, and retain a useful answer for future missing references.

## Decisions

- Different hashes remain evidence of different revisions. Consolidation is
  enabled only by the explicit **Keep; delete others** action after comparison.
- Revalidate the selected survivor and every removed member by path, size,
  modification time, and SHA-256 before moving anything.
- Store quarantine runs beside the repository under `PIHTI-quarantine/runs`;
  move metadata sidecars with their CAD files.
- Record old paths, survivor, hashes, possible filename-based referrers, and
  manifest in `.agents/consolidation-ledger.jsonl`.
- Mark every row under a top-level folder associated with a merged PR. The PR
  badge is a review cue, not canonicality evidence.
- Distinguish orange PR-folder/PR-added deletion candidates from neutral
  `Edited PR` history on pre-existing files.
- Let collision review quarantine one selected revision as well as consolidate
  all non-survivors around one selected canonical revision.
- Treat cleanup submissions as immediate UI state, reject stale result paints,
  and make already-completed retries resolve through the recovery manifest.
- Balance removed-path and survivor emphasis in the recovery ledger.
- Group adjacent cleanup events into ten-minute collapsible sessions and add a
  sticky history/status/session-action rail. Keep restoration event-scoped.
- Name the empty merged-PR selection **No PR filter**.
- Keep manual cleanup responsive without weakening revalidation: reuse the
  metadata-validated inventory before the action, let the executor rehash the
  selected files, and defer the next inventory scan instead of hashing the
  whole workspace before and after every move.
- Apply successful manual cleanup locally in the duplicate list. Remove a
  resolved two-file card as a unit; update a larger card's member/hash counts
  and disable its now-stale cleanup signatures until the owner rescans.

## Changed

- Consolidation planning, execution, manifest history, and transactional restore.
- Duplicate-row consolidation action and PR-folder styling.
- Searchable `/removed` history; old part URLs return a 410 consolidation answer.
- Documentation, tests, and tool version 0.11.0.
- Removed the full-results refresh and whole-viewport opacity change from
  per-member and reviewed-consolidation actions. Rail counts now follow the
  optimistic local card state.

## Verification

- `pytest`: 192 passed.
- `ruff check`: passed.
- `git diff --check`: passed (line-ending conversion warnings only).
- `mkdocs build --strict`: passed.
- Local browser verification: the ICF70 collision showed three survivor actions,
  PR-origin badges on the two PR rows, and searchable removal history with
  restore controls. No CAD cleanup action was executed during verification.
- Recording review traced the long pause to two forced full-workspace SHA passes
  per action, plus the where-used walk; the global hash passes are gone. Browser
  verification after restarting `lab pihti` showed 33 live groups, the new
  member/file/hash hooks, full opacity, and no console warnings. No CAD cleanup
  action was executed during this verification.
