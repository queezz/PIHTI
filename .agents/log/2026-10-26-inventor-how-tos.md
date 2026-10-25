# Preserve learned Inventor workflows for fresh sessions

## Goal

Owner requested reusable how-tos from our work together so a fresh session
does not have to rediscover Inventor automation behavior.

## Changed

- Added .agents/inventor-how-tos.md, consolidating verified October 8–22
  COM recipes, coordinate frames and units, geometry proxies, rigid joints,
  workspace fasteners, independent copies, hierarchy changes, flexible-context
  orientation fixes, travel checks, saving and native visual verification.
- Recorded observed failure modes and successful alternatives, including
  automatic occurrence renaming, translation setters, driver grounding order,
  off-axis inferred origins and invisible-view activation.
- Linked nine existing source/log records; marked dimensional examples and
  old test results as historical, with live remeasurement required.
- Added discovery links to AGENTS.md and .agents/README.md.

## Verification and boundary

- Six Python snippets compiled for syntax without execution or COM attachment.
- All nine guide links resolve to existing repository files.
- Both cold-start discovery references checked; git diff --check passed.
- Internal documentation only: no published docs, runtime source, native CAD,
  owner metadata, services or mail stores changed. No software test rerun or
  live CAD mutation was needed to validate this documentation change.

## Next

Read the guide before future native Inventor edits. Extend it with newly
verified recipes and supporting evidence, preserving the distinction between
reusable methods and measurements tied to specific part revisions.
