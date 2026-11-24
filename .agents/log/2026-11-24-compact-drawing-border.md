# Replace the oversized JIS drawing grid

## Goal and changes

Queezz requested a smaller drawing border/title block without unused JIS
administrative fields, retaining item name, author as Kuzmin and the date.

- Added native `PIHTI plain A4` border and `PIHTI compact` title-block
  definitions in the bellows IDW. Applied the plain rectangular border to all
  23 sheets, removing alignment triangles. Replaced the 17 existing JIS blocks
  with a single 130 × 9 mm row; sheets that previously had no title block
  retain their existing assembly-page layout.
- The footer keeps associative sheet name, drawing author, creation date and
  sheet/total fields. Changed the drawing's Author property to Kuzmin; retained
  its original 2026/11/15 creation date rather than rewriting historical data.
- Freed approximately 30 mm of vertical space where the old block stood.
  No model geometry, dimensions, view positions or sourcing
  code locations changed. The compact footer is a local drawing resource,
  not a change to Autodesk's global JIS template.
- Regenerated raw and workshop PDFs, including all nine MonotaRO links through
  the existing post-export publishing recipe.

Curated changes: `bellows-probe/Bellows-Monotaro-A4-JIS.idw`,
`bellows-probe/Bellows-Monotaro-A4-JIS-man.pdf`,
`bellows-probe/monotaro-assembly-order.md`, and this log.

## Verification

- Verified PIHTI.ipj; initial document collection empty. Opened the drawing
  invisibly and saved only the IDW after native health checks. All references
  resolved, active feature/relationship health passed, all 373 drawing
  dimensions/centerlines/center marks attached, and views were current.
- The saved drawing copy reopened cleanly. After export, closed the task-owned
  invisible drawing and its released dependencies; final document collection
  empty, matching the starting session.
- Doctor/STEP before and after unchanged: 1,080 models, 1,075 current mirrors,
  four stale, one missing and the same two unrelated BoronProbe reference
  findings documented in the preceding logs. IDW-only changes introduced no
  model mirror staleness.
- Native border bounds are x=10–287 mm, y=10–200 mm on all 23 A4 sheets.
  Rendered the full PDF and reviewed the contact sheet and representative
  English/Japanese footers. Confirmed 17 original-date fields, no printed
  `queezz`, PDF Author=Kuzmin, 23 pages and nine sourcing links. The link
  insertion helper verified unchanged page text and saved URI annotations.
- Gates: 536 tests passed, 7 skipped (100.17 s); Ruff and `git diff --check`
  passed. No published documentation or MkDocs configuration changed.

## Handoff

The compact resources remain reusable within the native IDW. Continue using
the existing line-weight and product-link publication steps for future PDFs.

## Follow-up: remove supplier instructions and fix both PDF outputs

Removed the two Japanese notes telling the shop to click/search MonotaRO
order codes and avoid duplicate orders, as requested. Both notes are absent
from native sheet 23 and both regenerated PDFs. Sumatra had the unsuffixed
PDF open; the previous pipeline added links only to the workshop `-man.pdf`.
Now both public PDF filenames receive nine link annotations, with the
unlinked export kept temporary. Updated the publication recipe accordingly.
Verified the revised sheet visually in Sumatra, then clicked code 33040156:
Chrome opened the SBC SBI20FL2K1+1060N MonotaRO product page. This is an
actual viewer click check in addition to structural verification of all nine
annotations. Native health and saved-copy checks passed again after note
removal. Closed the task-owned invisible drawing; no documents remain loaded.
