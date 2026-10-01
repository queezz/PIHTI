# STEP simulation viewer completion — 2026-10-01

## Goal and decisions

Resume the STEP simulation viewer handoff in the correct CAD repository.
queezz requested implementation continuation live in chat; the pasted
orientation-only packet no longer limits the session (owner decision 2026-10-01).
Review and land the existing v0.30.0 implementation without repeating its
completed full suite or browser walk. No implementation changes were needed.

## Changed

Commit only the viewer modules, template, JavaScript, shared viewer integration,
CSS, navigation, dependency/version changes, empty simulation map, tests,
README instructions, changelog, AGENTS dependency command and both handoffs.
README.md contains the feature documentation missing from the prior staging
list; README_SHORT.md has no diff. Hardware edits, folder moves and the rename
ledger remain outside this commit.

## Verification

- Reviewed the complete simulation modules, UI assets, tests and integration diff.
- External pihti-dedup environment imports v0.30.0 from the renamed checkout.
- Simulation and version tests: 4 passed in 3.14 seconds.
- Ruff src/tests/scripts/find_duplicates.py and git diff --check passed.
- Prior handoff supplies the full gate: 502 tests, JavaScript syntax, strict
  MkDocs and the browser Perimeter Walk. No product changes since that gate.
- No service started or stopped, no real part metadata assigned, no outbound mail.

## Next and limits

Load the new backend through the ordinary-terminal lab pihti service workflow.
Real hardware needs reviewed names, materials and electrical roles before a
simulation bundle can be exported. Large owner assemblies remain unverified;
Escape reset retains the prior handoff's browser verification limitation.
Prior synthetic scratch remains at its recorded location outside Dropbox;
its marker convention was not changed in this completion pass.

## Usage receipt

Provider: OpenAI; model: GPT-6; task: STEP viewer completion; child agents: 0.
Worked directly because this was a bounded review and commit continuation.
Provider usage: unavailable.
