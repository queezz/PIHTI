# Student submission author credits — 2026-10-01

## Goal and decisions

Credit merged student work using Git branch authors rather than the merge author.
PRs #1 and #3 credit nobuya0829; no full personal name inferred. PR #2 credits
shusukedochi, matching the existing Shusuke Dochi README credit. Credits apply
to submission work, not reused components or later archive curation.

## Changed

Added authored READMEs to BoronProbe_2026/ and Plasma Vessel_2026/ with author,
PR links, representative commits and review-boundary context. Added PR #2
provenance to bwllows-probe/README.md. That README stays uncommitted with the
pre-existing bellows/ deletion and bwllows-probe/ move; do not stage the move
or unrelated hardware, rename ledger or viewer work in this task.

## Verification

Three first-parent merges: 328d9ba (#1), 0de6360 (#2), 2e29170 (#3). Checked
branch commit authors and affected folder history. Ruff and whitespace checks
pass. Full pytest result appended below. No published docs changed; MkDocs
not applicable. No CAD cleanup, staged import or CAD edits performed.

## Next

Commit the two new root READMEs and this log. Include the edited bellows README
when the pending folder move is committed by its owning session.

Usage receipt: OpenAI / GPT-6, student-author credits; child-agent count 0;
provider usage unavailable.

Full pytest: 502 passed in 57.61 seconds.
