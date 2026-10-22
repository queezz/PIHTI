# Add the existing CF70 weld flange to the front pipe end

## Goal and evidence

Owner confirmed the left/front exposed yellow pipe end, beyond the o-ring
gland, and identified PALP/Prototype-PALP-CF70-34-hole-flange.ipt as the
candidate. Measured its bore at nominal 34 mm, matching the Mizuno pipe's
34 mm OD. The pipe ID is 28.4 mm (2.8 mm wall). The flange already is tracked.

## Changes

- Reused the identified flange without changing its source geometry.
- Added it inside bellows-probe/mizuno-pipe.iam, rigidly joined to
  pipe-for-mizuno-probe:1 so it follows the moving probe pipe.
- Joint CF70 weld flange to pipe end - rigid seats the pipe's front end
  at the flange inner land (native flange Y=5.1816 mm). Sealing face points
  outward, away from the pipe length, following the existing pipe example.
- Saved mizuno-pipe.iam, preserving pre-existing owner edits in that file.
  Other owner CAD and metadata changes remain outside this checkpoint.

## Verification

- Rigid joint healthy; seat centers coincide exactly in the native model.
- Flange sealing axis dot pipe inward axis = -1, confirming outward orientation.
- All active constraints and joints healthy in the pipe subassembly and both
  sliding-assembly and PIHT-Bellows-probe after update.
- Native bitmap inspected: flange on the exposed front end beyond the gland.
- git diff --check passed. No software changed; same-session Ruff and 525-test
  pass remain applicable to unchanged tooling.

## Fabrication boundary

The model uses nominal 34 mm bore and OD, with zero nominal clearance. No
machining tolerance, weld gap, weld preparation or weld bead was specified.
Shop fit tolerance remains to be chosen; the sealing geometry was preserved.
