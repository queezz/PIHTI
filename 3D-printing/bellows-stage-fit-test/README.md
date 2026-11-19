# Bellows stage mounting parts - print fit-test bundle

Fine-resolution STL exports from the current bellows-probe mounting design.
Import at **100% scale in millimetres**. The table links directly to each STL.

Print one of each for a reference set (12 pieces). For mounting one complete
carriage on two guide blocks, print **two guide spacers**. The full-stage
column lists the installed quantities (25 pieces across these 12 part types).

| Drawing sheet | Part / STL | Reference set | Full stage | Bounds X × Y × Z, mm |
| --- | --- | ---: | ---: | --- |
| 05 | [Front carriage foot](monotaro-front-flat-carriage-plate.stl) | 1 | 1 | 246 × 56.8 × 15 |
| 06 | [Middle carriage foot](monotaro-middle-flat-carriage-plate.stl) | 1 | 1 | 246 × 56.8 × 15 |
| 07 | [Rear carriage foot](monotaro-rear-flat-carriage-plate.stl) | 1 | 1 | 246 × 56.8 × 15 |
| 08 | [Guide spacer](SBI20FL-flat-spacer-15.stl) | 1 | 6 | 63 × 56.8 × 15 |
| 09 | [Thrust support block](monotaro-thrust-support-block.stl) | 1 | 2 | 62 × 20 × 50 |
| 10 | [Rear nut saddle](monotaro-TR16-nut-holder.stl) | 1 | 1 | 50 × 33.5 × 31 |
| 13 | [Thrust backing plate](monotaro-thrust-backing-plate.stl) | 1 | 2 | 99.5 × 60 × 10 |
| 14 | [Rear nut keeper](monotaro-TR16-nut-keeper.stl) | 1 | 1 | 50 × 33.5 × 5 |
| 15 | [Thrust spacer](monotaro-TR16-end-thrust-spacer.stl) | 1 | 1 | 22 × 22 × 3 |
| 16 | [End retaining washer](monotaro-TR16-end-retaining-washer.stl) | 1 | 1 | 22 × 22 × 3 |
| 17 | [Flange clamp upper](flange-clamp-114-upper.stl) | 1 | 4 | 196.175 × 87.5 × 20 |
| 18 | [Flange clamp lower](flange-clamp-114-lower.stl) | 1 | 4 | 196.175 × 87.5 × 20 |

## Printing and fit checks

- Lay a broad flat face on the bed. The carriage feet are 246 mm long;
  check bed clearance including the brim. Keep scale at 100% for fit checks.
- The source geometry is unchanged. Holes and bearing/nut seats retain their
  CAD sizes; no shrink compensation or FDM clearance has been added.
- Cosmetic tapped threads export as smooth bores. These prints are for fit
  checks and reference at the machine shop. Use the current dimensioned
  drawings for machining specifications.
- The paired flange clamps retain the designed 5 mm split gap. Print one
  upper and one lower for a single clamp test fit; four pairs serve the stage.

## Scope and provenance

Includes the three carriage feet, guide spacer, screw thrust-support block
and backing plate, TR16 nut saddle and keeper, end spacer and retaining
washer, and both clamp halves. The long table, lead screw, rails, profiles
and purchased hardware are outside this small-parts bundle.

The sheet numbers match the current 19-sheet bellows shop set. Native source
parts remain under `../../bellows-probe/`. The two previously exported clamp
STLs now live here, with identical bytes, so the bundle is self-contained.

`manifest.json` records native paths and hashes, STL hashes, millimetre bounds,
quantities and mesh checks. Exports use 0.005 mm absolute linear deflection
and 1 degree angular deflection from current solid STEP copies. All 12 meshes
passed the closed-edge test and were rendered for visual review.
