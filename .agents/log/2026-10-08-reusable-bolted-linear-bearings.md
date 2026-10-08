# Use a reusable four-bolt linear bearing unit

## Goal

Finish the floating M5 bolt connections to the violet bearings. The owner
suggested a reusable bearing subassembly with four bolts, used at all bearings,
with rigid joints and the same 15 mm gap as existing examples.

## Changes

- Created bellows-probe/linearbearing-bolted.iam through the running Inventor
  session under PIHTI.ipj. Contains one linearbearing.ipt and four existing
  AS 1420 Metric M5 x 20 bolt occurrences. Assigned a distinct assembly part number.
- Built the master from linearbearing:7 and its four already positioned bolts.
  Migrated their existing joint origins through native browser demotion, then
  converted the two rotational joints to rigid. All four master joints have
  JointType 102401 and Gap 1.5 cm, matching the owner's 15 mm examples.
- Grounded the bearing inside the master. Its instances are ungrounded and rigid
  subassemblies, allowing each bearing carriage to move as before.
- Replaced all eight direct bearing occurrences in
  bellows-probe/two-section-bellows-on-bearings.iam with the same master file.
  Used temporary single-bearing assembly containers and native demotion before
  replacement to preserve referenced bearing geometry and external relationships.
- Removed the 24 superseded top-level M5 bolts in the combined assembly and five
  superseded bearing M5 bolts in sliding-assembly.iam. Four original bolts remain
  inside the master; its eight instances provide 32 bolts. This also eliminates
  the duplicate bearing-hole bolt present across the two assembly levels.
- Temporarily grounded the existing non-M5 components during restructuring,
  restoring their original states afterwards. Layout remained unchanged.
- Saved the master, combined assembly and outer sliding assembly. Temporary
  assembly containers were closed and their files removed; no temporary
  references remain. Original IPT geometry was not edited in this task.

## Verification

- Read-only inventory before changes: 1732 files, 35 hash groups, 16 renamed hash
  groups, 23 same-name/same-size groups and 17 same-name/different-size groups.
- Trial creation/replacement was rolled back before final work. Combined assembly
  and master update successfully; active relationships are healthy. Eight instances
  each contain five components and four rigid 15 mm joints. All direct references
  resolve and the three saved documents report clean.
- Positions of all existing non-M5 components stayed exactly unchanged; fixed
  matrix error was below 3.3e-27 during final restructuring.
- Temporary combined-assembly driver tested -1, -10, -5 and 0 mm central carriage
  motion. Actual travel matched within 2.9e-9 mm, and all 32 bolts stayed fixed
  relative to their bearings within 3.6e-11 cm. Rolled back the driver, verified
  exact restoration of bearing/bolt positions and saved the restored pose.
- Combined assembly: 35 occurrences, 58 constraints and 18 joints. Master: five
  occurrences and four joints. Outer assembly: 17 occurrences, 20 constraints,
  ten joints.
- Python source is unchanged from the preceding 522-test passing gate and Ruff
  run in this chat. Whitespace checked. No tool version or published docs change.

## Existing outer-assembly issue

Opening sliding-assembly revealed four broken joints whose OriginTwo geometry
references the middle carriage plates the owner removed while adopting the
double plate: Rigid:5 and Rigid:6 (M6 bolts), Rigid:21 and Rigid:23 (lead-screw
nuts). Their geometry intents cannot resolve. These same four failures persist
after rolling back the initial trial and after the final bearing replacement;
no new outer relationship failures were introduced. Did not suppress or retarget
these joints during the bearing task. The outer assembly therefore still fails
Update2 despite the combined bearing mechanism passing its motion check.

## Next

Reconnect the four outer middle-carriage joints to the owner's new plate geometry
when working on its lead-screw connection.
