# Flatten the combined bellows assembly

## Goal

The owner clarified that the combined assembly must contain direct parts rather
than two section containers, to design a special middle connection and end
plates for the M16 lead screw. Geometry design remains the owner's work.

## Changes and decisions

- Flattened bellows-probe/two-section-bellows-on-bearings.iam to 42 direct part
  occurrences through the running Inventor session under PIHTI.ipj.
- Native promotion would empty the shared section definition and affect both
  instances. Tested this in a rollback transaction. Instead made two independent
  temporary native assembly copies with Inventor SaveAs(copy), replaced each
  section occurrence with its own copy, promoted their components through the
  native browser API, then deleted the empty containers. Temporary files were
  removed after verifying there were no remaining references to them.
- Kept the existing part-file references; flattening does not duplicate part
  geometry. The owner can replace specific middle/end occurrences directly.
- Temporarily grounded the four parent lead-screw nuts to prevent solver drift
  during promotion; restored their original states. No former internal section
  anchors remain grounded in the flattened assembly.
- Saved the combined assembly and its referring sliding-assembly.iam. Original
  bellows-clamped-on-bearings.iam was not saved or edited. Reopened it invisibly
  through Inventor to verify it still contains 21 occurrences and reports clean.
- Background COM automation performed the work. SilentOperation was temporarily
  enabled only for saving and restored afterwards.

## Verification

- Read-only duplicate inventory: 1729 files, 35 hash groups, 16 renamed hash
  groups, 23 same-name/same-size groups and 17 same-name/different-size groups.
- Final combined assembly has 42 parts, 68 constraints and 22 joints. Parent
  sliding-assembly has 22 occurrences, 20 constraints and 15 joints. Native
  updates succeed, active relationships are healthy, direct references resolve,
  both saved documents report clean, and no temporary copy references remain.
- Combined-document component matrices changed by at most 1.40e-10. In the parent
  context, positions and fixed orientations stayed within 1.08e-9; external
  components stayed within 1.34e-9. Existing free rotations on two sleeves and
  one rotational bolt in the second section may differ between contexts.
- Temporary parent-context driver tested -1, -10, -5 and 0 mm carriage travel.
  Actual displacement matched the command within 3e-9 mm; all four clamp/flange/
  tube clusters maintained relative positions within 1e-6 cm. Rolled back the
  driver and restored the starting pose before saving. No mouse drag was tested.
- Inventor automatically disconnected empty temporary document objects after
  promotion; cleanup encountered this after the completed transaction. A separate
  check verified references, health and native updates before saving successfully.
- Python source is unchanged from the preceding 522-test passing gate and Ruff
  run in this chat. Whitespace checked. No published docs or tool version change.

## Next

The owner will create the middle connection and special end plates. Existing
repeated parts still share their underlying IPT definitions; unique geometry
should use distinct replacement part files for the intended occurrences.
