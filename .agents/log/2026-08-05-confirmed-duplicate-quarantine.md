# Commit confirmed merge duplicate quarantine

**Date:** 2026-08-05
**Goal:** Commit only the duplicate CAD removals explicitly applied through the
PIHTI review tool, separately from the tool release.

## Decisions

- Treat the cleanup as CAD archive curation, not a `pihti-dedup` version bump.
- Commit the 41 workspace removals in their own change: 40 byte-identical members
  introduced by PR #1 and one individually reviewed PR #3 bearing member.
- Keep the recovery manifests under ignored `.pihti-dedup/quarantine/`; Git's
  parent commit is the portable recovery surface.
- Do not infer a canonical design from equality. This commit records only that
  each removed member had at least one byte-identical survivor named by the
  validated cleanup plan.

## Changed

- `BoronProbe_2026/parts/` — two confirmed duplicate members removed from the
  Inventor workspace.
- `Plasma Vessel_2026/Cathode-Anode-Flange/` — 27 confirmed PR #1 duplicate
  members removed.
- `Plasma Vessel_2026/Plasma-Flange-2024/` — 12 confirmed PR #1 duplicate
  members removed.
- `.agents/CHANGELOG.md` — recorded the archive cleanup milestone.

## State

- Both manifests report `references_checked: true` and require a post-apply
  assembly-resolution check in Inventor.
- Revalidation covered all 41 entries: every workspace source is absent, every
  quarantined byte hash matches its manifest, and every named survivor exists
  with the same SHA-256.
- The post-cleanup read-only inventory scans 1,218 CAD files and reports 63
  repeated-filename groups: 35 exact-copy groups and 28 collisions, plus 9
  different-name exact-copy groups.
- Tool gates remain green: 28 tests passed, Ruff passed, changed Python files
  passed the format check, strict MkDocs passed, and `git diff --check` passed.

## Next

- Open the affected top-level assemblies through `PIHTI.ipj` and verify that
  Inventor resolves the surviving paths after cleanup.
- Continue collision review; different-byte groups remain untouched.
