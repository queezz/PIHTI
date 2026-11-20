# Reduce the clamp toe rounds to R3

## Goal and diagnosis

Kuzmin questioned the lower R6 toe annotation and requested smaller outer
rounds that merely remove sharp corners. Inspection confirmed the old model
had two different toe rounds: Fillet2 / d22 = R6 and Fillet4 / d29 = R8.
The dimensions reflected those actual curves. Use R3 for both toe rounds;
retain the distinct R6 hand-opening corners.

## Changed

- `bellows-probe/flange-camp-114.ipt`: d22 and d29 changed to 3 mm.
  Other radii, 75 × 15 hand opening, Ø114.5 clamp bore and screw pitches
  remain unchanged.
- Updated both derived clamp parts, their current STEP mirror exports and
  the native bellows IDW. Sheet 17 now shows both toe radii as R3; sheet 18
  also follows the new R3 geometry. All radius dimensions remain attached.
- Updated both STLs in `3D-printing/bellows-stage-fit-test/`, plus manifest
  source/export hashes, bounds and README. Both maximum widths changed
  from 196.1747 to 200.5670 mm because the smaller rounds retain more material.
  The hole-center spacing remains 166 mm.
- Published the regenerated, line-weight-corrected 19-sheet PDF at the
  established local `bellows-probe/Bellows-Monotaro-A4-JIS.pdf` path.
  Preserved the separate owner manual PDF and unrelated assembly changes.

## Verification

- Master and derived features healthy (11778), no missing references.
  Volumes: master 294.413018, upper 126.576341, lower 167.836678 cm³;
  derived volumes sum to the master within 0.000001 cm³.
- Both meshes use 0.005 mm absolute / 1 degree angular deflection. Upper:
  577,928 triangles; lower: 69,016 after removing two zero-area triangles
  with coincident vertices. Both bounds 200.567 × 87.5 × 20 mm and every
  welded edge has exactly two incident facets. All 12 bundle manifest source
  and STL hashes match the files.
- Rendered both updated clamp sheets at high resolution and both STL halves.
  The drawing reopens clean: 138 dimensions and 69 centerlines attached.
  Raw/thinned PDF extracted text matches; 132 line widths adjusted.
- Initial Inventor owner set was empty. Initial cleanup encountered dependent
  documents because the master was opened before the drawing. A dependency-
  scoped, parent-first cleanup closed the drawing and then derived parts;
  verified zero task-owned documents remain. Subsequent reopen validation
  also used parent-first cleanup. No owner command was stopped.
- Final Doctor/STEP review: zero active reference blockers; the three edited
  part mirrors are current. Whitespace check passed. No software changes or
  software test rerun needed.

## Next

Reload both clamp STLs in the slicer. Use the updated PDF with R3 toe rounds
and the 200.6 mm rounded overall-width dimension for the fit-test revision.
