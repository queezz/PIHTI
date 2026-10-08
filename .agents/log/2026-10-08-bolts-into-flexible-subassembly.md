# Move clamp bolts into the flexible subassembly

## Goal

Move the seven owner-selected bolts from sliding-assembly into
bellows-clamped-on-bearings and investigate separation during movement.

## Decisions and changed paths

- Used the running Inventor automation API in the owner context after restarting
  Codex recovered its failed Windows tool launcher. The owner prefers background
  automation over interactive UI control.
- Native BrowserPane.Reorder moved three M5x20 and four M10x30 occurrences and
  their seven joints into bellows-probe/bellows-clamped-on-bearings.iam.
- Inventor renumbered the M5 occurrences from 5/8/6 to 1/2/3, and the M10
  occurrences from 3/4/1/2 to 1/2/3/4, respectively. Part files were untouched.
- Temporarily grounded lead-screw-nut-preview:1 during restructuring to prevent
  arbitrary axial carriage movement, then restored its original ungrounded state.
- Saved the subassembly and bellows-probe/sliding-assembly.iam through Inventor.
  Flexible remains enabled. Other open assemblies were not saved.

## Verification

- PIHTI.ipj was the active project. All direct document references resolve.
- Parent occurrence count changed from 27 to 20; child count from 14 to 21.
  Joint counts changed from 20/4 to 13/11, preserving all 24 joints.
- All parent and child constraints and joints report healthy; native updates pass.
- Maximum flexible-instance matrix change was 2.5e-11 for bolts and 2.2e-14 for
  existing subassembly components. Both saved documents report clean.
- Diagnostic restructures and a temporary constrained-motion test were rolled
  back. The motion test failed to solve and establishes no motion repair.
- Repository gates: 522 tests passed in 45.57 seconds, Ruff and whitespace checks
  passed. The first test attempt could not create its sandbox TEMP fixtures;
  retrying in the owner context with a fresh external temporary root passed.
- Read-only inventory: 1,724 files, 35 hash groups, 16 renamed hash groups,
  23 same-name/same-size groups, 17 same-name/different-size groups. No file
  cleanup or canonical selection was performed. No published docs changed.
- Existing owner edits in the two requested binary assemblies were preserved
  when saving. The separate modified PIHT-Bellows-probe assembly was left alone.

## Next

The bolt move is complete. Separation during dragging remains unverified and
unfixed. The owner was asked whether the two carriage ends should move relative
to each other or the entire subassembly should travel rigidly. Keep flexibility
and existing internal relationships until that intent is established.
