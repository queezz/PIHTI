# STEP face colours and fine viewport meshes

## Goal

Fix polygonal curves and inconsistent colours reported in catalog inspector screenshots.

## Decisions and changes

- The occurrence reader previously chose one face colour as the whole part colour.
  Preserve every face appearance and its triangle range instead. Saved explicit
  occurrence colours still override every face. Occurrence picking and isolation
  retain one ID per named part.
- Match the existing fine inspector settings: 0.01 mm linear deflection and
  0.15 radians angular deflection, replacing 0.3 mm and 0.5 radians.
- Changed simulation_step.py, simulation_web.py, viewer3d.js and simulation.js;
  bumped tool version to 0.30.2 and added coloured-cylinder regression coverage.

## Verification

- Full suite: 503 passed. Ruff, JavaScript syntax and whitespace checks passed.
- Real STEP mirrors read without modification: C40FC-A-Step.ipt has eight
  face colours and 54,503 triangles; DC Jack Panel Mount Base.ipt four colours
  and 83,088 triangles; PL08.ipt three colours and 13,079 triangles.
- Browser verification used Lab scratch step-test on port 48943, a copy of
  the optic STEP in the retained temporary workspace, and no owner service restart.
  The optic displays red, dark grey and metal faces with readable engraving;
  selection, isolation and Fit model work. Catalog uses the same renderer.
- Closed the test browser tab. Verified scratch listener PID 26948 under
  launcher PID 37160, stopped the Lab process tree, and confirmed the listener
  and both processes absent. Retained the temporary workspace as test evidence.
- Original Inventor files and STEP mirrors were not changed. Unrelated CAD
  edits and rename ledger remain outside this commit.

## Next

Restart pihti in Helm to load the fix. CPU contention affects responsiveness,
not these tessellation settings or stored colours. Fine meshes may take longer
to build and retain the existing triangle cap.
