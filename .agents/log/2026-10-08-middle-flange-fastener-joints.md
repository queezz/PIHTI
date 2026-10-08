# Finish the middle flange bolt and nut joints

## Goal

Fit the seven remaining loose M8 bolt/nut pairs around the middle flanges,
matching the owner's already placed pair with rigid joints.

## Changes

- Used the running Inventor session under PIHTI.ipj to edit
  bellows-probe/two-section-bellows-on-bearings.iam in the background.
- Matched the owner's AS 1427 Metric M8 x 45 bolts and AS 1112 (2) Metric M8
  Type 5 nuts. Retained all eight existing occurrences of each hardware part.
- The owner's placed bolt had Slider:1, while its nut had a rigid joint.
  Converted that slider to rigid as requested. Preserved the existing seating
  faces, origin points, flip settings and zero gap from both example joints.
- Created seven additional bolt joints on bellows_flange:1 and seven nut joints
  on bellows_flange:4. Derived origin points from their eight circular holes,
  radius 4.2165 mm, and matched opposite-face holes by assembly X/Z coordinates.
- Named the 16 joints Middle flange bolt/nut 1 through 8 - rigid. All use rigid
  JointType 102401 and zero gap. Existing non-M8 layout and grounding unchanged.
- Saved the combined assembly. Recorded the owner's new native hardware files
  ContentCenter/Fastners/M8x45-HexCS.ipt and ContentCenter/Fastners/m8-nut.ipt as
  required dependencies; these files were placed by the owner and not edited.
  No other native parts or outer assembly were saved in this task.

## Verification

- Read-only inventory before modification: 1736 files, 35 hash groups, 16 renamed
  hash groups, 23 same-name/same-size groups and 17 same-name/different-size groups.
- Trial joint creation at another hole was rolled back before final changes.
- Native updates succeed; all active relationships are healthy. Sixteen middle
  fastener joints are rigid, healthy and zero gap. Existing non-M8 positions
  stayed exactly unchanged. Direct references resolve and the saved document
  reports clean. Final assembly has 51 occurrences, 58 constraints and 34 joints.
- Temporary driver tested -1, -10, -5 and 0 mm middle-carriage travel. Every bolt
  and nut stayed fixed to its respective flange within 5e-10 cm. Rolled back the
  driver and verified exact position restoration before saving.
- Inspected an Inventor bitmap preview: loose hardware is fitted around the
  middle flange; existing carriage layout is retained. Preview is temporary.
- Python source is unchanged from the preceding 522-test passing gate and Ruff
  run in this chat. Whitespace checked. No tool version or published docs change.

## Next

Continue the owner's middle connection design. The previously documented broken
outer-assembly joints to the removed carriage plates remain outside this task.
