# Assembly-first Doctor and Git filename archaeology — pihti-dedup 0.13.0

**Goal:** repair imported generic names and missing Inventor references in the
assembly that gives them meaning, rather than hunting globally by filename.

## Decisions

- Keep filename-wide collision safety, but make the assembly the navigation and
  working context. Inventor still resolves repeated names workspace-wide; the
  UI must never claim a colliding path is the intended component.
- Retain both directions of the reference scan. The existing name → referrers
  index now also exposes document → embedded names without reading assemblies a
  second time.
- Treat direct missing, ambiguous, and generic names as assembly problems.
  Specific names with one current workspace target stay out of the work queue.
- A web-side rename does not edit an `.iam`. The old name deliberately remains
  visible until the owner explicitly repoints and saves the assembly in Inventor.
- Search exact basenames through every reachable Git ref. “Never tracked” is a
  useful answer: it redirects the search toward STEP/import or external Content
  Center sources. Git evidence is read-only and cannot silently restore CAD.
- Every historical Inventor occurrence receives a preview. A Git rename whose
  destination still exists links to that file and supplies its absolute path.

## Changed

- Added Assembly Workbenches to `/doctor` and
  `/doctor/assembly/<assembly-path>` with assembly/candidate previews, missing
  evidence, direct-name scope, and a persistent safe-workflow rail.
- Preserved assembly context through guarded filename rename sessions and return
  navigation.
- Added Unicode-safe, NUL-delimited Git filename history, historical blob reads,
  cached historical preview serving, and URL-encoded filename alias folding.
- Bumped the tool to 0.13.0 and updated user documentation and tests.

## Verification

- `pytest`: 204 passed.
- `ruff check`: passed.
- JavaScript syntax check: passed.
- MkDocs strict build: passed (the existing unlisted `how-to-pr.md` notice and
  upstream Material for MkDocs 2.0 warning remain informational).
- `git diff --check`: passed (line-ending conversion warnings only).
- Live browser: `C25K22A4CU.iam` grouped the encoded and decoded Japanese name,
  reported `W5K22A4CU.iam` and its parts as never tracked, and showed no broken
  previews or horizontal overflow. `BoronProbe_2026_non-bellows.iam` showed the
  two Git events for `ICF70-34-hole.ipt`, both historical previews, and the
  current `ICF34-through.ipt` destination.
- No CAD file was renamed, restored, or otherwise modified during verification.
