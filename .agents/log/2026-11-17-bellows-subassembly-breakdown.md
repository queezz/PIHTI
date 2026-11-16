# Subassembly breakdown and plain party names in the bellows set

- Goal: queezz asked for every page to start with its number and for a
  subassembly breakdown on the parts sheet, so each balloon number links to
  the table and what to make, and how many, is easy to check. Two follow-ups
  set the wording:
  - "Owner" means Kuzmin.
  - The machine shop is 工作室. Polite business Japanese such as 当方支給
    and 御社手配 is wrong for these drawings.
- Inventor had no documents open at the start. The IDW was opened invisibly
  and each sheet edited in its own transaction. Zero documents were open at
  handoff.

## Subassemblies from the model

Leaf occurrences of `sliding-assembly-monotaro.iam`, grouped by occurrence
path:

| Letter | Model subassembly | Parts to manufacture |
| --- | --- | --- |
| A | Bed module, without D | 02, 07 ×2, 09, 10, 11 ×2, 13, 14, 15 |
| B | Front module | 03, 06 ×2 |
| C | Middle module | 04, 06 ×2 |
| D | Rear driven carriage, inside the bed module | 05, 06 ×2, 08, 12 |

The rear vacuum module holds no manufactured parts. The letter columns sum to
the totals; the script asserts this before building the table.

## Changed in the IDW

- **Headings.** Pages 1–3 and 17 now start with their number, like pages
  4–16:
  - `BP-MON-17   PARTS TO MANUFACTURE`
  - `BP-MON-16   ASSEMBLY ISOMETRICS`
  - `BP-MON-15   ASSEMBLY AND SUPPLIED HARDWARE`
  - `BP-MON-01   SOURCING REFERENCE`

  "BELLOWS STAGE" moved to the line below each heading.
- **BP-MON-17 view captions:**
  - `A  BED (WITH D)`
  - `B  FRONT FIXED MOUNT`
  - `C  MIDDLE FLOATING MOUNT`
  - `D  REAR CARRIAGE` (was "REAR DRIVE")
- **BP-MON-17 parts table.** Rebuilt with the columns No., Part, A, B, C, D,
  Qty, Material and Stock, titled "A–D: QTY PER SUBASSEMBLY". Stock reads
  工作室 or Kuzmin.
- **BP-MON-17 balloons.**
  - The 09 balloon moved from beside 08 on the D view to beside 12 on the bed
    view. The model fits the nut on the lead screw in the bed module, and the
    D view's model does not contain it.
  - 12 belongs to D but is ballooned on the bed view, where D is shown fitted.
  - 05 and 08 moved 3.5 mm left to make room for the wider table.
- **Wording:**
  - BP-MON-15 reads "KUZMIN SUPPLIES / ASSEMBLY HARDWARE", "WHEEL END /
    ASH125 FROM KUZMIN" and "工作室: drill and tap …".
  - BP-MON-01 names Kuzmin and 工作室 in its three headers and two notes.
  - BP-MON-09 and BP-MON-10 say their stock comes "from Kuzmin (MonotaRO …)".

## Verification

- The overlap check is clean on the edited sheets: 1–3, 11, 12 and 17. An
  early pass showed the lettered B and C captions touching, so all four
  captions went to 2.7 mm text.
- Rendered pages 1, 3, 11 and 17. The Japanese text renders through Inventor's
  fallback font, Malgun Gothic, embedded in the PDF.
- Reopened the saved IDW invisibly: no missing references; 112 dimensions and
  38 centerlines attached; clean.
- Shop PDF thinned with `pdf-strokes --pages 4-17` (97 widths). Its text is
  identical to the raw export.
- A test export inside an open transaction left a modal "Publish Inventor File
  to DWF" prompt that blocked the script. Pressing Accept released it, and the
  aborted transaction left the drawing unchanged. The real exports ran under
  `SilentOperation` with no prompt.

## Open

- Whether to add Japanese labels such as 材質 and 数量 next to Material and
  Qty. Not done without queezz's terms.
- Earlier owner decisions stand: material grades, bearing-seat and journal
  fits, and the rail-pitch tolerance.
