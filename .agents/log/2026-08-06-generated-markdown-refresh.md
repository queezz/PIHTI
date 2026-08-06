# Generated Markdown refresh — pihti-dedup 0.7.2

**Date:** 2026-08-06
**Agent:** codex gpt-5
**Goal:** fix the generated folder-document system rather than treating one
authored Bellows note as the whole Markdown problem.

## Diagnosis

- The repository contained 36 marker-owned generated folder READMEs, all still
  on the May-era template and notice.
- `write_generated()` recognised the ownership marker but skipped both manual
  and generated existing files. Template improvements therefore had no migration
  path.
- The old template rendered file lists followed by empty Purpose, Notes, and
  Status headings whose content existed only as invisible HTML comments.
- A normal dry run also entered staging and vendor `Design Data/` and
  `Templates/` trees and proposed new documentation there.

## Changed

- Marker-owned outputs now refresh; marker-free authored notes remain immutable.
- Existing marker-owned READMEs are refreshed even when their folders no longer
  meet today's new-file heuristic.
- Added `--refresh-only` to update existing generated files without creating
  any README or INDEX.
- Simplified the generated README to title, explanation, main assembly,
  assemblies, and parts. Removed empty authoring placeholders and the redundant
  main-assembly star.
- Excluded staging, caches, save history, and vendor support trees.
- Used a reviewed refresh-only run to migrate all 36 generated README files and
  `INDEX.md`; no new document was created and `bellows/README.md` remained
  classified as manual.

## Verification

- Post-migration inventory: 36 generated READMEs, zero old notices, zero old
  placeholder templates.
- A second refresh-only dry run reported all generated outputs current.
- Browser QA on `/folder/BoronProbe` showed the generated inventory as
  structured Markdown with no empty sections or duplicate main marker.
- Full suite: 173 passed.
- Ruff (including the generator), `git diff --check`, and strict MkDocs passed.
- Scratch QA PID and port 4198 were verified gone; the owner's service was not
  touched.
- No CAD file was modified.
