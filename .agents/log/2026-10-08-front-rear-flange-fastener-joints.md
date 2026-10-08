# Finish the front and rear flange fastener joints

## Goal

Fit the remaining M8 bolts and nuts in the upper sliding-assembly.iam, using the
owner's placed pair at each end as the template.

## Changes

- Used the running Inventor session in the background under PIHTI.ipj.
- Retained the owner's two already fitted bolt/nut pairs. Added fourteen bolt
  joints and fourteen nut joints to finish eight pairs per end, sixteen pairs
  total. All 32 end-flange fastener joints are rigid and have zero gap.
- Front templates: Rigid:29 to CF114-CF70-zero-length-adappter:2 and Rigid:28
  to nested bellows_flange:3. Rear templates: Rigid:30 to adapter:1 and Rigid:31
  to nested bellows_flange:2. Copied their seating faces, native origin points,
  flip settings and gap, locating the remaining radius-4.2165 mm flange holes.
- Matched nut-side hole centers to bolt-side centers in upper-assembly X/Z,
  using the nested flexible occurrence transforms. Named the joints Front/Rear
  flange bolt/nut 1 through 8 - rigid.
- Temporarily held non-M8 top-level occurrences grounded during fitting and
  restored their original states. Saved only bellows-probe/sliding-assembly.iam;
  hardware parts and the nested assembly definition were not edited or saved.

## Verification

- Read-only inventory before modification: 1737 files, 35 hash groups, 16 renamed
  hash groups, 23 same-name/same-size groups and 17 same-name/different-size groups.
- The owner had repaired the previously documented broken middle-plate joints:
  upper-assembly Update2 succeeds and all active relationships are healthy before
  and after this task. Direct references resolve and the saved document is clean.
- Checked all existing non-M8 top-level and nested component positions; maximum
  change during fitting was 1.13e-8 cm. Existing carriage layout was preserved.
- Temporary driver tested front-carriage travel of -1, -10, -5 and 0 mm. Actual
  travel matched within 8.3e-10 mm. All end bolts/nuts remained attached to their
  respective direct or nested flange faces within 5.3e-9 cm. Rolled back the
  driver and verified exact fastener-position restoration before saving.
- Final upper assembly has 47 occurrences, 20 constraints and 40 joints.
  Inspected an Inventor bitmap preview: all end hardware is fitted and no loose
  M8 fasteners remain. Preview is temporary evidence.
- Python source is unchanged from the preceding 522-test passing gate and Ruff
  run in this chat. Whitespace checked. No tool version or published docs change.

## Next

Continue the owner's lead-screw and middle connection design.
