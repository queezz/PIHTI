# Keep central bearings upright in flexible contexts

## Goal

Fix the two inverted middle bearings in PIHT-Bellows-probe without removing
the sliding assembly's flexibility.

## Findings and change

- Units linearbearing-bolted:1 and :3 were upright in the native two-section
  assembly and sliding-assembly, but rolled 180 degrees in the higher assembly.
- Flush:28 and Flush:29 locate the units against a side plane of the double
  carriage plate. Their normals follow the rail axis, allowing the roll.
- Added Central bearing 1 upright and Central bearing 3 upright: flush each
  bearing unit's YZ origin plane to the double plate's XY origin plane with
  -35 mm offset. Existing joints and constraints remain in place.
- Saved two-section-bellows-on-bearings.iam, sliding-assembly.iam and
  PIHT-Bellows-probe.iam through the running Inventor session. These files
  already contained owner changes; saving preserves the complete live state.

## Verification

- All eight bearing units upright in both flexible parent contexts.
- All active constraints and joints healthy; assembly updates succeeded.
- A temporary grounded driving nut moved the middle carriage exactly 10 mm
  while its bearings stayed upright. Transaction aborted afterward.
- Restored original sliding-context carriage positions after trial solves;
  higher-context bearing positions were unchanged by the correction.
- Inventor bitmap inspected, confirming the middle bearings seated below
  the carriage plate in the higher assembly.
- git diff --check passed. No Python or published documentation changes.

## Next steps

No remaining work for this orientation correction. Other owner CAD edits,
rename ledgers and simulation changes remain outside this task.
