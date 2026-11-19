# Fix false Doctor references and require proactive review

## Goal and diagnosis

Kuzmin requested that agents inspect Doctor proactively before final CAD
saves/exports and fix the catalog warnings he showed. The two bellows
blockers were extraction bugs, not absent CAD geometry:

- `sliding-assembly-monotaro.iam`: physical sector-boundary scan returned
  `leeve-6.ipt` instead of `monotaro-telescope-sleeve-6.ipt`.
- `monotaro-bed-module.iam`: the scan spliced unrelated property bytes onto
  the end-washer filename. Reading logical `UFRxDoc` streams recovers
  `monotaro-TR16-end-retaining-washer.ipt`.

## Changes

- `whereused.extract_filenames` reassembles OLE streams with the existing
  olefile dependency before scanning. Non-OLE byte fixtures retain the
  original scan. Damaged OLE files raise a scan error rather than producing
  misleading partial names.
- Regression tests build a real fragmented CFB container, verify a name
  across non-contiguous sectors, ignore unallocated directory bytes and
  report malformed OLE data. Existing real-missing-name gates remain intact.
- AGENTS.md and inventor-how-tos.md require baseline Doctor review, loaded
  native-health checks before final save, and a refreshed saved-file review
  before exports/commit. Documentation-only work stays out of Inventor.
- Bumped the dedup tool to 0.37.1 and updated its changelog. No native CAD
  files or reference-verification/deferral ledgers were edited.

## Verification

- 15 focused where-used tests passed.
- Full repository suite: 543 passed in 117.52 seconds.
- Ruff and whitespace checks passed.
- CLI STEP mirror status: zero active Doctor blockers, down from two.
- Restarted only the catalog through `lab restart pihti`; read live Doctor
  and STEP mirror pages and verified v0.37.1, zero blocked references and
  both bellows assemblies ready to export. Old failures remain in history.
- Existing archive-wide Doctor findings and the two deferred student
  assemblies were inspected and preserved. Their source-package gaps and
  duplicate-folder decisions already have open directions.

## Next

Kuzmin reported native PLD items failing to render interactive 3D despite
existing STEP mirrors and requested a dedicated catalog review. Added
catalog-review-next.md and linked it from directions.md with reproduction,
scope, current findings, background timeout snapshot and acceptance checks.
No diagnosis of the PLD rendering failure has been asserted yet.
