# Align preanode screen and ignition help

## Goal
Align the XZ origin planes of preanode-screen:1 and ingnition-help:1 so each
contains the simulation assembly Z axis.

## Decisions and changes
Worked in the active pihti-for-simulation-flat.iam under PIHTI.ipj. Preserved
both existing mates, translations and axial heights. Rotated each occurrence
about its local Z axis to the radial plane containing its mounting center and
the assembly Z axis. Added a hidden named radial work plane and a zero-offset
mate for each XZ plane. Original part documents remain untouched.

The active assembly was already dirty. Left the successful change unsaved for
user inspection, so this log is the only saved repository change for the task.
No STEP was exported from the unsaved document.

## Verification
Both original mates and the new mate on each occurrence report healthy (11778).
Translations remained unchanged within floating point precision. World XZ plane
normals are perpendicular to assembly Z and their plane distances to the assembly
origin are below 1e-7 cm. Earlier attempts were transactionally rolled back.

## Next steps
Inspect in Inventor, save the assembly when ready, and allow the mirror to export
the saved revision.
