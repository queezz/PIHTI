# Annotate the bellows shop drawing for machining

- Goal: work the [readability review](2026-11-16-bellows-drawing-shop-readability-review.md)
  into `bellows-probe/Bellows-Monotaro-A4-JIS.idw` through COM. queezz
  asked for the style fixes to be automated too.
- Inventor 2027.1 had PIHTI.ipj active and no documents open. The IDW was
  opened invisibly, so all 90 loaded documents were task-owned. Each sheet was
  edited in its own transaction. The IDW was saved with `Save2(False)` before
  each review export to the scratch folder, and closed afterwards. Inventor was
  back to zero documents at handoff.

## Changed in the IDW (fabrication sheets 5–17, sheet 1 title only)

- **Section-line letters.** They print `A`/`B` at 4.5 mm instead of `A / .`.
  The cause was a sheet-reference format in the template's view annotation.
- **Section labels.** They are native `A-A ( 2 : 1 )` labels at 5 mm. Each is
  placed clear of dimension text and lines, notes, views and the title block.
  The typed `A–A 3:4` notes are gone.
- **Centerlines.** Automated centerlines added 20 hole and bore axes in plans
  and sections. Six symmetry axes were added after a mirror test on each view.
  Centerlines went from 16 to 40.
- **Thrust support block (BP-MON-07).**
  - Changed from 1.35:1 to 1:1.
  - New dimensions: axis height 30, and Ø18, Ø26.2 and Ø28 on the section.
  - The counterbore is now a hole note on the bolt face.
  - Five prose lines removed.
- **Rear nut saddle (BP-MON-08).**
  - Keeper face and section moved to 2:1.
  - New dimensions: Ø18.2, 15, 12.5, 6, 25.2, 38, 3.3 and R3, plus an M4
    thread note.
  - Foot face: 25.5 and a hole note.
  - Six prose lines removed.
- **Lead screw (BP-MON-10).**
  - 1:1 with a break from 110 to 930 mm, sections at 2:1, cutting lines
    retrimmed.
  - New dimensions: flat 6 and 10, 11 across the flat, pilot 10, and a full
    M5 thread note.
  - Four prose lines removed.
- **Middle foot (BP-MON-04).**
  - Pocket dimensioned: 65, 24.4 (= 4 from the centerline), R3, 6.5.
  - The three stacked `4 × Ø6 THRU` notes became one `2 × Ø6 THRU` with two
    leaders, plus `2 × Ø6 THRU, CBORE Ø12 × 6.5 DEEP`.
- **Smaller fixes.**
  - BP-MON-09: Ø30 dimension replaces the stock prose.
  - BP-MON-05: pilot depth folded into the M5 note.
  - BP-MON-02: the two identical countersink callouts merged into `20×`.
  - BP-MON-11: M5 pitch added.
  - BP-MON-12: cutting lines shortened and dimensions moved clear.
- **Headers and title block.** Headers read `BP-MON-xx PART` and `Material: …
  Qty: n`; REV letters and `Machining review` were removed. Every sheet is
  named `BP-MON-xx Part`, and the title block shows the sheet name. Spacer and
  washer quantities (1 each) come from BP-MON-01.
- General notes on the fabrication sheets went from 80 to 47 and dimensions
  from 88 to 110. Every new dimension's value matched the prose it replaced.

## Verification

- Reopened the saved IDW invisibly. No reference was missing, and none of the
  110 dimensions or 40 centerlines was detached. The drawing was clean and was
  closed.
- Rendered all 17 sheets of the final review export at A4 and checked them.
- At queezz's request, re-exported the Git-excluded
  `bellows-probe/Bellows-Monotaro-A4-JIS.pdf` from the saved IDW. Applied the
  same documented stroke mapping as before to pages 5–17:
  - 96 width operators changed (0.54/0.72/1.08/1.44/1.98/3.42 pt to
    0.39/0.48/0.63/0.88/1.16/1.55 pt), matching the parsed count on each page.
  - No unexpected widths and no images on those pages.
  - Text identical to the raw export, page boxes unchanged, pages 1–4
    pixel-identical.
  The rewrite used a standard-library script in the session scratch folder;
  it is not committed. Inventor was back to zero documents after the export.
- No tooling changed, so the pytest and Ruff gates do not apply.

## Not done

- Cover sheets 1–4 are unchanged: prose cover, isometrics and hardware page.
  A balloon isometric with a native parts list remains open, as does the
  question of whether owner assembly instructions belong in the shop set.
- Owner decisions: material grades, which are still "(reference)", and fits
  on the 6001ZZ seat, the 51101 recess and the Ø12 journals.
- BP-MON-02 still uses chain dimensions and two text lines for its 56 holes.
  The ASH125 wheel tap still has no drawing.
- The feet sections stay rotated in the lower left without a rotation mark.
  `UNDERSIDE 3:4` remains a typed note.
