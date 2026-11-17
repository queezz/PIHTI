# Subassembly breakdown, page numbering and plain names in the bellows set

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

- Earlier owner decisions stand: material grades, bearing-seat and journal
  fits, and the rail-pitch tolerance.

## Revised the same day: names instead of letters, number = page

queezz could not read the A–D letters and did not find them on the part
sheets. queezz also asked what `BP-MON` means: "Bellows Probe, MonotaRO", a prefix
Codex invented that appears nowhere on the drawings. queezz chose "number = page"
from three options and said the shop understands "Material" and "Qty", so
no 材質 or 数量 was added.

- **Subassemblies by name.** The letter captions and the A–D columns were
  removed. Each view is captioned with its name and its parts listed below:
  - FRONT CARRIAGE: 05, 08 ×2
  - MIDDLE CARRIAGE: 06, 08 ×2
  - REAR CARRIAGE: 07, 08 ×2, 10, 14
  - BED: 03, 04, 09 ×2, 11, 12, 13 ×2, 15, 16, marked "(with rear carriage)"

  The table is back to No., Part, Qty, Material and Stock. The lists were
  asserted against the table totals.
- **Part sheets.** Each Qty line ends with where the part goes:
  - "Qty: 6 (2 per carriage)"
  - "Qty: 2 (bed)"
  - "Qty: 1 (rear carriage)"

  "Aluminum 6061" became "A6061", the JIS name the table already used. This
  also cleared a new overlap with the thread note on the rear foot sheet.
- **Renumbered so the drawing number is the page number:**

  | Old | New |
  | --- | --- |
  | BP-MON-17, -16, -15 | 01, 02, 03 |
  | BP-MON-02 to -14 | 04 to 16 |
  | BP-MON-01 | 17 |
  | Balloon 15, ASH125 wheel tap | 03, the page with its tap detail |

  - Sheet names, title blocks, headings, balloons and table rows changed in
    one transaction per sheet. The table is sorted by the new numbers.
  - Every prose reference now reads `No. nn`, including ranges such as
    "No. 04 to 10 and 13 to 16". The ASH125 sourcing line now points to
    No. 03.
- Repo docs: the how-to house style now states number = page, plain
  subassembly names, and no invented prefixes or letters.
  `sourcing/monotaro-sbc-guides.md` cites "No. 08 in the bellows shop set".
  Earlier logs keep the BP-MON numbers they were written with.

### Verification

- The overlap check is clean on all 17 sheets except the long-standing hit on
  No. 14: cutting letter A against the 18.5 extension line, not visible in the
  render.
- Rendered pages 1, 7 and 17. On page 1 the first bed list ran into the clamp,
  so it was rewrapped to three lines.
- Reopened the saved IDW invisibly: no missing references; 112 dimensions and
  38 centerlines attached; clean. Zero documents were open afterwards.
- Shop PDF thinned with `pdf-strokes --pages 4-17` (97 widths). Its text is
  identical to the raw export and contains no "BP-MON".
