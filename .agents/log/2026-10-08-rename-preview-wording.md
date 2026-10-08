# Clarify the rename preview when no assembly repair is needed

## Goal

Explain whether the owner's Doctor rename panel indicates a failure and fix its
wording when Inventor finds that assemblies use a different same-named copy.

## Findings

The screenshot is the pre-rename confirmation, not a failure or completed rename.
PIHTI-for-Boron uses the surviving BoronProbe/BoronProbe.iam, not the selected
staging/hayashi/SpectroscopySystem/Probe/BoronProbe.iam. No assembly reference
requires changing when renaming the staging file. Confirmed the staging source
still exists and BoronProbe-Hayashi.iam does not; no real CAD rename was executed.

## Changes

- `_repair_confirm.html` now explains that no files have changed yet. A fully
  checked preview with no applicable references says Ready to rename, explains
  that no assembly references need changing and offers Confirm rename. It uses
  a green status panel rather than the amber warning treatment.
- Clarified other-copy and unchanged-assembly wording. Previews requiring repair
  retain the review/repair choices and open/error states do not get a ready claim.
- `_repair_pending` derives the ready state from structured Inventor inspection
  results. Open targets/referrers, inspection errors and matching references
  prevent that state. Confirmation retains the Inventor session and confirmation
  fields so unaffected referrers are accounted for in the rename ledger.
- Added round-trip regression coverage for an unused same-named copy: preview
  makes no changes; confirmation renames only the selected file, leaves the
  other assembly bytes unchanged and settles its not-applicable referrer.
  Added open/error cases that must retain the warning/manual choice.
- Bumped the tool to 0.34.4 and recorded the milestone. Restarted the tracked
  PIHTI viewer with lab restart pihti so it loads the update. Inventor was not
  restarted and no CAD files or assembly references were modified by this task.

## Verification

- Full suite after implementation: 523 passed in 52.74 seconds. After adding the
  two open/error guard cases, the focused Doctor suite passed all 26 tests.
  Every test uses fake Inventor sessions, never the owner's running session.
- Ruff and git diff --check passed. Published docs unchanged; no MkDocs gate.
- Live service status confirms version 0.34.4 after restart. Original staging
  filename remains present and the proposed destination remains absent.

## Next

Refresh the viewer and submit the rename again to see the clarified preview.
The owner decides whether to confirm the actual rename.
