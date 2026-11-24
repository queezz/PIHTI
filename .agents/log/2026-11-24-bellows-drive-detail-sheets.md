# Explain the bellows-stage drive assembly

## Goal

After confirming the MonotaRO order was placed, the owner requested updated
Inventor/PDF drawings with explanatory subassemblies for screw supports,
under-table backing and nut mounting, plus a numbering review.

## Decisions and changed paths

- Updated `bellows-probe/Bellows-Monotaro-A4-JIS.idw` from 19 to 23 sheets.
  Added 19 wheel-end screw support, 20 vessel-end retainer, 21 support block
  to table, and 22 rear carriage nut mounting. The sourcing sheet is now 23.
- Kept fabrication pages/numbers 04–18 and the existing cover balloons stable.
  Number 03 still supplies the handwheel machining instructions. Refreshed the
  cover routing note and sheet 03 assembly index/hardware list.
- New views remain native, associative Inventor views: local isometrics,
  shaft sections, underside/end views, and a keeper-hidden view exposing the
  machined TR16 nut. Component leaders attach to actual drawing-curve intents.
  Drawing-only component visibility changes do not change assembly geometry.
- Updated the sourcing rail-screw code to 41519256 and its 40-piece purchase
  quantity. Sheet 03 lists fitted quantities rather than all purchased spares.
- Sheet 21 explicitly distinguishes the ordered hardened Ø6.4 × Ø17 × 3 washer
  from the existing modeled Ø6.6 × Ø18 × 2 envelope. BUMAX 109 M6 nuts are named
  in the assembly instructions. No native hardware substitution, bearing/preload
  approval or new drive load rating is implied; retain the basket's fit/load
  qualifications. Assembly must check contact, engagement and preload.
- Regenerated `Bellows-Monotaro-A4-JIS.pdf` and the workshop
  `Bellows-Monotaro-A4-JIS-man.pdf`. Thin-line remapping applies only to
  fabrication pages 04–18, preserving shaded assembly views.
- Added the owner's order-placed confirmation to `monotaro-basket.md`; the
  audit remains historical evidence because no final receipt was provided.

## Native session and verification

- Verified `PIHTI.ipj` before automation. Recorded all loaded documents before
  editing. The pre-existing drawing was dirty; its starting state was saved as
  an ignored staging backup before editing. Preserved pre-existing documents
  and their model state. Native IDW saves used `Save2(False)`.
- All native references resolved. Active model features and assembly
  constraints/joints were healthy; suppressed historical features and the two
  suppressed drawing-position constraints were not treated as failures.
- All 364 existing dimensions, centerlines and center marks were attached;
  every drawing view was current. No new fabrication dimensions were introduced.
- Opened an on-disk copy of the saved IDW invisibly for a clean-load check,
  avoiding closure of the owner's pre-existing drawing. It opened clean with
  23 sheets and no missing references, then was closed. No task-owned new
  documents remained and no loaded documents were dirty after export.
- Rendered all 23 final workshop pages. Reviewed the overall set and the new
  pages at readable size, correcting cropped placement, callout crossings,
  section-label formatting and title-block collisions. Raw/shop PDF text is
  identical; both are 23-page landscape A4 files.
- Refreshed saved-file Doctor/STEP status after native save: 1,080 in-scope
  models, 1,075 current mirrors, four stale and one missing, unchanged from the
  starting review. Two unrelated Doctor blockers remain: C25K22A4CU's missing
  `ICF70F 1個付き 19穴.ipt` and BoronProbe_2026_non-bellows' missing
  `ICF70-34-hole.ipt`. Stale mirrors are BoronProbe_2026_non-bellows,
  sliding-assembly, two-section-bellows-on-bearings and
  PIHT-Bellows-probe-monotaro. The affected stage/bed/carriage mirrors are
  current; IDW-only edits introduce no new model mirror staleness.
- Gates: 536 tests passed, 7 skipped (91.15 s); Ruff passed;
  `git diff --check` passed. No published documentation or MkDocs config changed.

## Next

Use the workshop PDF for assembly explanation and the existing fabrication
sheets for machining. Resolve the already documented support-hardware fit and
load qualifications at assembly/release; no unrelated CAD cleanup was performed.
