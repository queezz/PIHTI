# Match bellows stand-ins to 135–485 mm flange spacing

## Goal and diagnosis

The owner specified 135 mm minimum and approximately 485 mm maximum flange
spacing for each bellows. Mate:9 and Mate:25 already had enabled -485 mm to
-135 mm limits on the opposing flange faces. Four 200 mm stand-in pipes per
bellows could not telescope far enough to represent the compressed endpoint.

## Changes

- Created instead-of-bellows-100mm.ipt as an independent native copy of the
  original stand-in. Set extrusion length d1 to 100 mm and its part number
  to instead-of-bellows-100mm. Original instead-of-bellows.ipt is unchanged.
- Replaced the eight stand-ins in two-section-bellows-on-bearings.iam with
  the short part, retaining their existing flange joints and occurrence names.
- Added one extra section to each bellows, giving five sections per bellows.
- Suppressed Mate:18 and Mate:34, which directly joined the former middle
  sections, and added a concentric mate plus two limited overlap mates for
  each extra section. Changed existing sliding overlap limits to -100–0 mm.
- Kept the existing flange travel limits enabled at 135–485 mm. Saved the
  new native part and edited assembly through Inventor under PIHTI.ipj.
- Parent assemblies were updated and checked, but not saved because they
  contain existing live owner changes outside this task.

## Verification

- Native endpoint trials: (135,135), (485,485), (135,485), (485,135) mm.
  To command exact trial positions, temporarily disabled the two flange
  limits and drove their mate offsets. Measured flange spacing matched all
  four targets within 0.0001 mm; all active relationships were healthy.
  Aborted each trial transaction, restoring the prior pose and enabled limits.
- All active parent assembly relationships healthy after update. Both bellows
  in each flexible parent context measured within the specified range.
- Final assembly: 53 direct occurrences, 66 constraints, 34 joints.
- Inspected an Inventor bitmap of the resulting five-section stand-ins.
- git diff --check passed. No software changed; the preceding same-session
  M10 task's Ruff and 525-test pass remain applicable to the unchanged code.

## Limits

These overlapping pipes remain visual/kinematic stand-ins for flexible
bellows; they are not a proposed telescopic tube manufacturing design.
No changes to the earlier single-section source assembly or original pipe.
