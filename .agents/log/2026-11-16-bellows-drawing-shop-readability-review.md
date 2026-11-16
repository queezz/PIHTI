# Review the bellows shop PDF for machine-shop readability

- Goal: read `bellows-probe/Bellows-Monotaro-A4-JIS.pdf` (17 A4 sheets, local
  export, Git-excluded) the way a machinist would. Compare it with the sets in
  `Drawings-PDFs/` that were submitted to the shop and fabricated. Sets
  checked: Cathode-flange-parts, Plasma-Box-Windows and its correction,
  VF65-KF40-adapter, boron-target-cell and -grooved, the mesh holder and
  palp-desk.
- Rendered every sheet at A4 and zoomed into suspected collisions. Checked
  duplicate text from the raw PDF text order. No CAD file, IDW or Inventor
  session was touched.
- Learned house style recorded in
  [inventor-how-tos.md](../inventor-how-tos.md#house-style-from-shop-accepted-drawings).

## Set-wide defects

1. Section-line letters print as `A / .` in oversized text on every
   fabrication sheet. The `/ .` looks like an empty field in the cutting-line
   label format, so one style fix should clear it. On BP-MON-10 the two B labels
   overlap as `B / .B / .`.
2. Every title block reads `Bellows-Monotaro-A4-JIS`, and only author and date
   are filled. The part name, number, material, quantity and scale sit in loose
   text at the top left. The accepted sets show the part name in the title
   block.
3. Geometry is written as prose instead of dimensions. Examples are the
   BP-MON-04 pocket, BP-MON-05 M5 depth, all BP-MON-07 bores, the BP-MON-08
   bore, pocket and M4 pattern, and the BP-MON-10 flat and tap. The machinist
   has to rebuild these from sentences.
4. Centerlines are missing where symmetry carries the dimensioning:
   - BP-MON-09 section axis
   - BP-MON-11 hole pattern and section
   - BP-MON-07 section bores
   - the BP-MON-02 to -05 sections
5. Section views float. They are neither projected from nor aligned with
   their parents, and their labels are small text below the view
   (`A–A 3:4`). House style is `A-A ( 3 : 4 )` above the view.
6. A first issue carries revision letters B–F and a `Machining review` status.
   The shop never received revisions A–E.
7. The material is ambiguous. Aluminum parts read `Aluminum 6061
   (reference)`, and the steel grade is missing on BP-MON-13 and -14.
8. Bearing and journal seats have no fits. These are the BP-MON-07 Ø28 seat
   (6001ZZ OD), the Ø26.2 recess (51101) and the BP-MON-10 Ø12 "nominal"
   journals. The accepted sets give limits where fit matters, e.g.
   `Ø18 h10 (18.00/17.93)`.
9. Sheets 1 and 4 are mostly text and mix owner assembly instructions into the
   shop set. House style is one isometric with balloons and a parts list.
10. The radial M5 tap in the supplied ASH125 wheel boss is a machining
    operation with no drawing. It is described only in prose on sheet 4.

## Per sheet

- BP-MON-02 table plate (p5):
  - The two CSK callouts (8× and 12×) have identical specifications.
  - The stacked 84 and 46 dimensions overlap near the holes.
  - The 115/145/40 and 27/17/40 chains cross each other.
  - The 60-pitch and 180-pitch rows are given in text without a first-hole
    offset.
  - `WHEEL END` floats.
  - With 56 holes, a hole table from a corner datum suits this plate.
- BP-MON-03 to -05 feet (p6–8):
  - The plan dimensions read well.
  - BP-MON-04 prints `4 × Ø6 THRU` three times in one place (three stacked
    leader notes in the PDF text). Its leaders reach two holes.
  - The BP-MON-04 pocket is given only as text.
  - BP-MON-05 `2 × M5 FROM UNDERSIDE` needs a thread depth and pilot on the
    note, not a separate `M5 PILOT DEPTH 11.5` line.
- BP-MON-06 guide spacer (p9): closest to house style; only the label defect.
- BP-MON-07 thrust support block (p10), the weakest sheet:
  - Ø18, Ø28 and Ø26.2, the axis height of 30 and the Ø11 × 6 counterbores
    exist only in text.
  - The section carries only 8, 20, 1.5 and 50, and 8 and 20 are cramped.
  - The bolt-face view shows only 46.
  - `BASE` and `BOLT ENTRY` float.
- BP-MON-08 rear nut saddle (p11):
  - There are three views, and the left one has no label.
  - 25 and 31 stack off the same edge.
  - The bore, pocket and M4 pattern exist only in prose.
  - This sheet needs a redraw.
- BP-MON-09 TR16 nut (p12): the section has no axis line, and the Ø30 stock
  size is text only.
- BP-MON-10 lead screw (p13):
  - At 1000 mm across the sheet the journals are unreadable. The Ø12
    dimensions are squeezed and the section letters collide.
  - Use a break view, end detail views at 2:1, flat 6–16 from the end and
    1 deep dimensioned on A-A, and the tap depth on B-B.
  - Both sections have no dimensions.
- BP-MON-11 thrust backing plate (p14):
  - Symmetry is implied, with no centerlines.
  - `4 × M5 THRU` omits the pitch.
- BP-MON-12 rear nut keeper (p15):
  - `B / .` collides with 33.5.
  - `C0.4 PERIMETER` overlaps the title-block line.
  - The bore is located only from a hole row (6), not from an edge or a
    centerline.
- BP-MON-13 and -14 (p16–17): no quantity; `Ø22 OD` is leader text rather
  than a dimension.

## Automation split

- Agent-automatable through COM: center marks and centerlines on every view
  (the bisector recipe exists), hole tables, the parts list and balloons, the
  BP-MON-10 break view, and native hole and thread notes in place of prose.
  A lint gate on the exported PDF or the IDW could catch stacked duplicate
  text, label collisions, text crossing the title block and long notes.
- Faster for queezz once in Inventor: the section-label format, title-block
  fields mapped to each sheet's model iProperties, text heights, and the view
  label format. Save them into the PIHTI template so later drawings inherit
  them.
- Owner decisions: bearing-seat and journal fits, definite materials, whether
  owner assembly instructions stay in the shop set, and a sheet for the ASH125
  wheel modification.

## Next

Settle the template and style fixes first. Agent passes after that should
start with centerlines and hole tables, run the lint, and re-render all sheets
at A4 before issuing.
