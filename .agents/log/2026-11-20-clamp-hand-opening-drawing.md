# Update the drawing for the 75 mm hand opening

## Goal and changes

Kuzmin requested the drawing update after the master/derived parts and print
export were changed to a 75 mm hand opening.

- Updated `bellows-probe/Bellows-Monotaro-A4-JIS.idw`, preserving its existing
  on-disk edits. Sheet 17 now has native attached 75 mm length and 15 mm
  height dimensions, an attached R6 corner-radius dimension and a horizontal
  hand-opening centerline.
- Removed the obsolete loose leader "SLOT 60 × 15, R6" found during the PDF
  review. Positioned the 75 mm dimension below the opening inside the bore
  clearance and the R6 leader to the left, clear of dimension text.
- Regenerated the 19-sheet PDF and published the line-weight-corrected
  `bellows-probe/Bellows-Monotaro-A4-JIS.pdf`. Its established local exclusion
  remains; the native IDW is the committed source. The owner's separate
  `Bellows-Monotaro-A4-JIS-man.pdf` was preserved.

## Verification

- Saved native drawing before PDF translation and re-saved clean afterward.
- Reopened clean; 138 dimensions and 69 centerlines attached; no missing
  references; sheet 17 has actual 75 and 15 values and no old 60 mm slot note.
- Rendered all 19 pages and inspected a contact sheet plus sheet 17 at high
  resolution. Corrected layout and stale note before final publication.
- Applied `pdf-strokes --pages 4-19`: 132 line-width changes. Extracted text
  is identical between raw and thinned PDFs.
- Doctor/STEP review: zero active reference blockers. The two owner-resaved
  clamp/rear-carriage assemblies have stale STEP mirrors, alongside earlier
  queue items. This drawing task did not edit or save those native assemblies.
- PIHTI.ipj verified. Initial Inventor document set was empty. All task-owned
  invisible documents were released after each pass, including errors; zero
  remained at completion. An inspection with an overbroad cleanup loop was
  rejected by automatic approval review before execution, then replaced by
  ownership-filtered cleanup.
- No software changes; native/visual checks and whitespace gate apply.

## Next

Use the revised PDF for the 75 mm hand-opening version. The fit-test STL
was already updated and committed with the preceding master-part edit.
