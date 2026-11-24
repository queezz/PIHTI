# Separate the purchased wheel and link the Japanese supply sheet

## Goal

Queezz identified that the cover's 03 wheel balloon and manufacturing-table
row misleadingly treated an assembly page as a part drawing and the purchased
ASH125 as a shop-made wheel. He also requested Japanese on the last page and
clickable MonotaRO links, allowing post-export PDF links.

## Changes

- Renamed sheet 01 to Fabrication drawing index. Its legend explicitly maps
  balloons to fabrication sheets 04–18. Removed the 03 wheel balloon, table
  row and bed-list entry. Changed the table heading to Parts to machine and
  its first column to Sheet. Repositioned the table inside the border.
- Added a separate purchased-handwheel note with ASH125 / 02033236, Kuzmin
  supply, M5 tapping only, and an explicit assembly-sheet-03 instruction link.
  The nut and screw remain listed because their supplied blanks need machining.
  Updated the corresponding wording on sheet 19.
- Translated sheet 23 into Japanese with native Yu Gothic UI notes. It separates
  shop stock/fabrication, purchased components and purchased parts needing
  additional machining. Clarified fitted quantities versus spares and the six
  guide blocks. Visible blue order codes remain usable on paper.
- Added nine URI annotations to the workshop PDF after native export and the
  fabrication-page line-weight pass. The raw Inventor PDF remains unlinked.
  Added a small publishing helper and normalized native-note-bound manifest,
  plus re-export instructions in `monotaro-assembly-order.md`. Future changes
  to sheet 23 code positions require regenerating those bounds.

Curated paths: native IDW, workshop PDF, `monotaro-assembly-order.md`,
`add-monotaro-pdf-links.py`, `monotaro-pdf-links.json`, and this log.
No model geometry or machining dimensions changed.

## Verification

- PIHTI.ipj active; initial Inventor document collection empty. Opened the
  drawing invisibly, checked native references/features/relationships before
  saving only the IDW. All 373 dimensions/centerlines/center marks attached;
  all views current. Saved-file copy reopened cleanly and was closed.
- After export, released the task-owned invisible drawing; dependencies closed
  with it. Final Inventor document collection empty, matching initial ownership.
- Doctor/STEP review before and after unchanged: 1,080 models, 1,075 current,
  four stale, one missing; the same two unrelated BoronProbe missing-reference
  findings recorded in the earlier 24 November logs. No new affected finding.
- Reviewed rendered cover and Japanese sourcing page, including Japanese
  glyphs, table border, label spacing and cross-references. All 23 PDF pages
  retain identical extracted text before/after link insertion. Verified all
  nine saved URI targets against the manifest and checked all nine annotation
  rectangles contain their actual printed code bounds from Poppler extraction.
- Public MonotaRO pages successfully resolved the rail set, loose block, 6001ZZ
  and TR16 nut codes. Other fetches hit tool cache/decoding errors; their audited
  product URLs from the basket remain the link targets. No stock/price recheck
  is claimed. Native note API documentation did not supply a hyperlink property;
  the owner's authorized PDF post-export approach was used.
- Gates: 536 tests passed, 7 skipped (92.11 s); Ruff passed including the new
  publishing helper; `git diff --check` passed. No MkDocs/published docs changed.

## Handoff

Use `Bellows-Monotaro-A4-JIS-man.pdf` for the clickable workshop set. Follow
the publication recipe when exporting again so product links are retained.
