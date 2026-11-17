# Bellows shop drawing, second pass

- Goal: act on queezz's review of the annotated set. The table plate was hard
  to read and the colour isometrics had heavy lines. Some dimensions still
  overlapped, and the rail hole pitch has to be obvious.
- Inventor had no documents open at the start. The IDW was opened invisibly
  and saved before each export. Zero documents were open at handoff.

## Changed in the IDW

- **Colour isometrics (sheets 2–4).** All 14,473 edge segments of the eight
  shaded views moved to a new `Visible Thin (ISO)` layer at 0.18 mm. The
  fabrication views keep the 0.5 mm visible line.
- **Table plate (BP-MON-02).**
  - Now 1:2.5 with a break from 170 to 1000 mm, so both ends and every
    special hole are readable.
  - Rail holes: `25`, an explicit `60` pitch, `17×60(=1020)` and the 175
    rail spacing.
  - Profile countersinks: `115`, `5×180(=900)`, then `20`.
  - End clusters: `145`/`10` and `10`/`27`. Rows 46/84/130/175/215 on the
    right, 1092 below, and short hole-note leaders.
  - Removed section A-A, which only showed the 10 mm thickness; the header
    now reads `Thickness: 10`, as on the shop-accepted plates.
  - Values the model holds at 144.98 or 26.98 display as whole millimetres.
- **Overlap fixes from a new automated check** (see how-tos):
  - Feet: counterbore leaders go to the left hole, clear of the A letter.
  - Lead screw: cut A moved to 13.8 mm from the end, still inside the flat;
    `VESSEL END` beside the shaft end; the set-screw note moved off the
    label.
  - Middle foot: 6.5 dimension moved.
  - Thrust block: 8/20 restacked and the cutting line retrimmed.
  - Saddle: 38/50 lifted, label lifted, cutting line retrimmed, M4 note
    re-anchored.
  - Keeper: 18.5 dimension and notes moved.
- The local Git-excluded shop PDF was re-exported and thinned with
  `pihti-dedup pdf-strokes --pages 5-17`. 96 widths changed, and the text is
  identical to the raw export.

## Verification

- Reopened the saved IDW invisibly: no missing references; 112 dimensions and
  38 centerlines, none detached; clean.
- The overlap check is clean on every fabrication sheet except one cosmetic
  touch on BP-MON-12: a cutting-line letter lies on the 18.5 extension line.
  The cut must pass through the bore centre, and Inventor fixes the letter
  beside it.
- Rendered the plate, lead screw, feet, saddle, thrust block, keeper and
  isometric sheets at A4.

## Open

- Cover: queezz asked whether to number the parts to manufacture. The
  recommendation is a balloon isometric with a native parts list as sheet 1,
  following the shop-accepted sets, with the sourcing list moved to the back
  for owner reference. Awaiting queezz's go-ahead.
- Unchanged owner decisions: material grades, the bearing-seat and journal
  fits, the rail-hole pitch tolerance, and a sheet for the ASH125 wheel tap.
