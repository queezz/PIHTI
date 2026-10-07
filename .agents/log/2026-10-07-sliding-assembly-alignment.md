# Sliding assembly alignment

## Goal and changes
In active bwllows-probe/sliding-assembly.iam, seated clamp-foot:2's local XY
origin/bottom plane on assembly XY with a named zero-offset flush constraint
and grounded it. Rigidly repositioned the connected assembly to preserve
relative geometry. Rotated both rail bwllows probe occurrences around their
cylindrical bearing axes so local +X points along assembly +Z, retaining their
opposing local Y directions. Grounded both rails to retain profile orientation.
Part documents were untouched. Assembly left unsaved for review.

## Verification
All 20 assembly constraints report healthy. Foot origin Z is zero within 1e-7 cm.
Both rail local X axes have assembly Z component 1 within 1e-7. Native update
succeeded. First attempt with both rail Y directions equal was rolled back;
retaining their original opposing length directions preserved Mate:9.

## Next steps
Inspect and save the active assembly when ready.
