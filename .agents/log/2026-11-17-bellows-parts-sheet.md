# Ballooned parts sheet for the bellows shop set

- Goal: queezz asked for the parts to manufacture to be numbered on an
  isometric, in the style of the shop-accepted sets. He also noted that the
  sourcing list on sheet 1 is mostly for him and for reference.
- Inventor had no documents open at the start. The IDW was opened invisibly
  and saved before the export, then saved again after it, because the new
  table recalculates during export. Zero documents were open at handoff.

## Changed in the IDW

- **BP-MON-17 is now the parts sheet (sheet 1).**
  - The subassembly isometrics were re-laid out: the bed across the top and
    the front, middle and rear-drive mounts below at 0.18.
  - The purchased vacuum-module view was removed; it is still on BP-MON-16.
  - Added the JIS title block.
- **Balloons.** The drawing-only `BP balloon` symbol has dot leaders to the
  nearest edge of each part, numbered with the BP-MON drawing number:
  - On the bed: 02, 07, 10, 11, 12, 15 (wheel tap), and 13/14 as a stacked
    pair at the screw end.
  - On the mounts: 03, 04, 05, 06, and 08/09 stacked, because the nut sits
    inside the saddle.
  - Native balloons were not used: they would enable the structured BOM in
    queezz's assemblies, which have uncommitted edits.
- **Parts table.** A drawing-only custom table lists No., part, quantity,
  material and who supplies the stock for 02–15. Quantities and materials come
  from the existing sheets. Materials keep the "(ref.)" marker until queezz
  decides the grades.
- **Sourcing list.** Moved to the back as `BP-MON-01 Sourcing reference`,
  headed "BELLOWS STAGE / SOURCING REFERENCE" with a pointer to BP-MON-17.
  Sheets 2 and 3 are named `BP-MON-16 …` and `BP-MON-15 …`.
- **New order:** BP-MON-17, -16, -15, -02 … -14, -01. The fabrication drawings
  are now pages 4–16.

## Verification

- Reopened the saved IDW invisibly: no missing references, 112 dimensions and
  38 centerlines attached, clean.
- Shop PDF re-exported and thinned with `pihti-dedup pdf-strokes --pages 4-17`
  (97 widths on 14 pages). Pages 1–3 carry shaded images and stay as exported.
  The text is identical to the raw export. Rendered pages 1 and 17 at A4.

## Open

- Owner decisions: material grades, bearing-seat and journal fits, and the
  rail-hole pitch tolerance.
- The ASH125 wheel tap (row 15) still has no drawing of its own; its detail is
  the prose on BP-MON-15.
