# Use workspace M10 bolts in the two-section carriage

## Goal and findings

Replace the machine-local M10 bolts with the owner's Dropbox-workspace part
and track that source in Git. PIHTI.ipj was active throughout.

The eight installed M10x30 occurrences resolved outside the workspace to
Inventor's machine-local Content Center cache. Eight newly placed, unconstrained
occurrences used ContentCenter/Fastners/M10x30-SHCS.ipt. Both part documents
had the same internal identifier and volume (4.008842863851201 cubic cm).

## Changes

- Through Inventor, replaced the eight installed occurrences with the workspace
  part. All eight existing joints and exact occurrence transforms survived.
- Removed the eight unconstrained loose copies after confirming they had no
  joints or constraints.
- Saved bellows-probe/two-section-bellows-on-bearings.iam, preserving the
  owner's pre-existing live changes in that document.
- Added ContentCenter/Fastners/M10x30-SHCS.ipt to the scoped Git checkpoint.
- Parent documents updated successfully but were not saved: the higher
  assembly already had unrelated live owner changes.

## Verification

- Read-only duplicate inventory: 1749 files, 35 hash groups, 16 renamed hash
  groups, 23 same-name/same-size groups, 16 same-name/different-size groups.
- Exactly one workspace copy of M10x30-SHCS.ipt was found.
- Saved assembly embedded M10 reference names contain only M10x30-SHCS.ipt;
  Inventor's direct descriptor resolves to the workspace file, not missing.
- Eight installed bolts remain, each with its original joint and zero change
  in its transform; constraint and joint counts are unchanged.
- All active relationships in the edited assembly and both open parent
  assemblies were healthy after update.
- Ruff and git diff --check passed; full pytest: 525 passed in 94.58 seconds.

## Limits and next steps

The file resides under the owner's Dropbox workspace. Dropbox transfer status
and resolution on the other PC were not observed. Existing metadata sidecar
changes are outside this checkpoint. No cache files were moved or deleted.
