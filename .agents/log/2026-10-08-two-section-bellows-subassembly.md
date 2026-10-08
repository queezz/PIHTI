# Combine the two bellows sections

## Goal

Put the owner's two bellows sections into one flexible subassembly. The owner
will draw the shared middle plate separately; no plate geometry was requested.

## Changes and decisions

- Created bellows-probe/two-section-bellows-on-bearings.iam through the running
  Inventor session under PIHTI.ipj, containing the two existing occurrences of
  bellows-clamped-on-bearings.iam. Both child occurrences and their new parent
  occurrence in sliding-assembly.iam remain Flexible and ungrounded.
- Used native browser demotion to preserve reference relationships. The existing
  inter-section Mate:29 migrated into the new document as Mate:1. Sliding-assembly
  now has 22 occurrences, 20 constraints and 15 joints. External hardware and
  lead-screw components stay in their existing parent assembly.
- Preserved the owner's saved second-section layout and existing native part
  edits. No component files were moved or renamed on disk, and the shared
  single-section definition was not saved or edited by this grouping operation.
- Saved the new assembly and sliding-assembly.iam. A locked Primary view warning
  interrupted the parent save; acknowledged it to complete the save. No new
  design view or appearance change was created.

## Verification

- Read-only duplicate inventory: 1727 files, 35 hash groups, 16 renamed hash
  groups, 23 same-name/same-size groups and 17 same-name/different-size groups.
- Trial demotion was rolled back first. Final demotion preserved all top-level
  and 42 nested component matrices to within 1.18e-9. Restored the two original
  ungrounded section states after Inventor automatically grounded the first
  demoted occurrence.
- Native updates succeed and active parent/wrapper relationships are healthy.
  Both saved documents report clean and their direct references resolve.
- A temporary parent constraint moved the central carriage through -1, -10,
  -5 and 0 mm. All four flange/clamp/tube clusters maintained their relative
  positions within 1e-6 cm. Rolled back the driver and verified the original
  pose before saving. The +1 mm trial did not solve; existing coupling and
  travel limits were left intact. This was an API motion check, not mouse drag.
- Python source is unchanged from the preceding 522-test passing gate and Ruff
  run in this chat. Whitespace checked. No published docs or tool versions change.

## Next

The owner can draw and place the shared middle plate in the combined assembly.
The two sections currently share one underlying single-section definition;
editing that definition affects both occurrences.
