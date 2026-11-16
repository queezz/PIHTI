# Cross-check the bellows parts against the MonotaRO sourcing

- Goal: queezz asked for the drawn parts to be checked against the MonotaRO
  sourcing.
- Sources:
  - `bellows-probe/monotaro-basket.md`, `sourcing/monotaro-drive-and-wheel.md`
    and `sourcing/monotaro-sbc-guides.md`;
  - the shop set's BP-MON-01 and BP-MON-15 lists and the BP-MON-17 parts table;
  - leaf occurrence counts from `sliding-assembly-monotaro.iam`;
  - axial positions measured in `monotaro-bed-module.iam`;
  - three MonotaRO listings read in the app browser. WebFetch got 403, and
    Claude in Chrome was not connected.
- Both assemblies were opened invisibly, measured and closed without saving.
  Zero Inventor documents were open afterwards. No CAD or sourcing file
  changed.

## Quantities: all match

- Model = basket = BP-MON-15:
  - Guides: 2 SBI20 rails and 6 SBI20FL blocks (2 sets of 2 plus 2 loose).
  - Rail and block screws: 36 M6×16 small-head, 24 M5×35.
  - Plate fixings: 20 DIN 7991 M5×16, 12 M5 T-nuts.
  - Thrust supports: 4 M6×75 10.9, 4 class 10 nuts, 4 hardened 6.6×18×2
    washers.
  - Other screws: 8 M5×20, 2 M5×40, 4 M4×12, 1 M5×10.
  - Bearings and drive: 2 6001ZZ, 2 51101, 1 split collar, 1 TR16 nut,
    1 screw stock, 1 ASH125.
- Model = BP-MON-17 table: the manufactured quantities 02–14.
- Not in the basket, reused per its note: 8 M10×30 clamp screws, 4 flange
  clamps, 24 M8×45 bolts with nuts on the CF flanges, rear-module vacuum
  hardware, and 2 Al 30×30 L1000 profiles.
- In the basket but not the model: the M5×12 flat-point wheel set screw
  (39281776).

## Catalogue against the model

| Code | Listing | Model and drawings |
| --- | --- | --- |
| 44848072 | TR16×3 RH round nut, 15割 type A, A = Ø30, B = 25, iron, plain, ¥779 | Nut envelope Ø30 × 25; BP-MON-09 matches |
| 44347055 | NTR16×1000, 3 mm pitch, RH, S45C, L = 1000, plain, ¥4,798 | BP-MON-10 material matches; overall length also 1000 (see below) |
| 06943316 | Iwata SCSS 1215S split collar, SUS304, Ø12 × Ø35 ±0.1 × 15 ±0.1, 2 × M6×18, ¥1,498 | Collar envelope Ø35 × 15 matches; no axial holding force listed |

The 6001ZZ (12×28×8), 51101 (12×26×9) and ASH125 (Ø12 H8, 22 mm boss)
figures come from the sourcing notes; their pages were not reopened. Seats
and stacks match them:
- Ø28 × 8 seat with the 6001 flush.
- Ø26.2 × 1.5 recess for the 51101.
- The screw end is flush with the ASH125 boss, so the 6–16 mm flat centres
  the set screw at 11 mm, mid-boss.
- At the vessel end the screw end sits 0.52 mm below the spacer face, so the
  washer clamps the spacer. The M5×10 engages 6.48 mm, inside the 7 mm
  minimum thread.
- Both journal shoulders sit 1.0 mm clear of the 6001 inner rings.

## Findings for queezz

1. BP-MON-10 dimensions the screw at 1000 overall, the same as the stock
   length, which leaves nothing for facing the cut ends. The function does not
   depend on overall length: the journals are measured from each end and the
   shoulders have 1 mm clearance. Options: show it as a reference `(1000)`
   with "face both ends", or give 996–998.
2. The BP-MON-08 nut pocket is 25.0 deep for a 25-long nut, with no tolerance
   listed: zero axial clearance against the keeper. The width already has
   0.2 clearance (25.2 for 25 flats). Options: 25.1–25.2, or "fit to the
   supplied nut".
3. The saddle's M5×40 screws pass through 33.5 of saddle and engage about
   6.5 mm (1.3D) in the A6061 rear foot. BP-MON-05 gives the 11.5 pilot but
   no thread depth.
4. BP-MON-01 lists 41519703 as "36". MonotaRO sells it in packs of 2, and
   the basket correctly says 18 packs. Typing 36 into Quick Order buys 72.
5. `sourcing/monotaro-sbc-guides.md` has drifted:
   - It still describes "integral 15 mm pads in the three feet"; the model
     uses six separate guide spacers (BP-MON-06).
   - It says mounting hardware is absent from the basket; the basket now
     lists it.
6. Minor: the Ø6 / CBORE Ø12 × 6.5 clamp-screw holes in the feet are larger
   than standard M5 sizes (Ø5.5 / Ø9.5). They work as drawn.
