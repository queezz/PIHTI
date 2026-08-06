# Folder-note Markdown presentation — pihti-dedup 0.7.1

**Date:** 2026-08-06
**Agent:** codex gpt-5
**Goal:** make the bellows folder note readable and prevent new folder notes
from repeating its unstructured Markdown shape.

## Diagnosis

`bellows/README.md` contained a bare title followed immediately by five
`label:value` lines. Markdown assigns no structure to either convention and,
without blank lines, correctly rendered the entire file as one paragraph. The
renderer and its safe-Markdown rules were behaving as designed.

## Changed

- Normalized `bellows/README.md` into a heading, purpose paragraph, secondary
  heading, and labelled Markdown list without changing its facts.
- Raised rendered-note prose and heading sizes, bounded line length, improved
  spacing, and placed the dedicated folder-page note inside a quiet contained
  surface.
- Added concise Markdown guidance and a valid multiline placeholder to the raw
  folder-note editor. The renderer remains standards-based and does not guess
  structure in arbitrary text.
- Bumped `pihti-dedup` to 0.7.1 and recorded the presentation contract.

## Verification

- Focused Markdown/web tests: 55 passed.
- Full suite: 169 passed.
- Ruff, `git diff --check`, and strict MkDocs build passed.
- Visual QA on the live bellows data confirmed separate title, purpose,
  Details heading, labelled facts, bounded measure, and editor guidance.
- QA used the scratch `lab` service on port 4198. Its PID and listener were
  verified gone afterwards; the owner's registered service was not touched.
- No CAD file was modified.
