# Clarify slots and the screw bearing stack for the shop

## Goal and owner input

The shop did not understand the slot shorthand. Queezz added explicit 3, 5.5
and 8.5 mm dimensions on sheet 07 and adjusted other dimensions, leaders and
section letters. He requested Japanese explanations and slot locations from
the plate centre. The shop also proposed h7 on sheet 12 and commented on the
9 mm thrust-bearing width. Queezz explicitly confirmed h7 was still only a
proposal, not an agreed machining tolerance.

## Changes

- Preserved the owner's current native drawing, including unsaved state, in
  an ignored staging backup before editing. Retained his slot shape dimensions,
  other dimension/leader edits and section-letter placement.
- Sheets 05–07 now call out `8か所 長穴 幅5.5 × 全長8.5 貫通` and explain
  R2.75 ends and 3 mm between arc centres. Replaced the 175/53 spacing chain
  with associative dimensions from the plate centre to slot centres:
  ±61 and ±114 horizontally, ±20 vertically. Measured every new native
  dimension and checked it against the projected slot geometry.
- Corrected sheet 06's horizontal centreline: it bisected two lower chamfer
  edges, 28.2 mm off centre. It now bisects the opposite outer plate edges.
  The vertical symmetry axis and all new datum dimensions are model-linked.
- Added Japanese notes on sheet 12 and sheets 19–20: 51101's complete width
  is 9 mm, including both washers and the ball/cage assembly; the modeled
  support recess is 1.5 mm, leaving 7.5 mm outside. This width is distinct
  from the 71/31 mm shaft machining lengths. 6001ZZ supports radial loads;
  the opposing 51101 bearings support the axial directions.
- Sheet 12 explicitly identifies Ø12 h7 as the shop's unconfirmed proposal
  and calls for the diameter tolerance to be settled before machining. Did
  not add h7 to either diameter dimension as an approved requirement. NTN's
  general thrust-fit table lists js6/h6, so h7 was not silently inferred from
  a generic bearing-fit recommendation.
- Regenerated the raw PDF and tracked workshop PDF from the native IDW.
  Used the established thin-line pass on fabrication pages 04–18 only.

Changed curated paths: `bellows-probe/Bellows-Monotaro-A4-JIS.idw`,
`bellows-probe/Bellows-Monotaro-A4-JIS-man.pdf`, and this log. The native file
includes the owner's edits that preceded this pass. No model geometry changed.

## Verification

- Confirmed PIHTI.ipj and recorded the pre-existing documents and dirty states.
  All native references and active feature/relationship health checks passed.
  All 373 dimensions/centerlines/center marks were attached; views were current.
- Saved only the drawing. A saved-file copy reopened cleanly with 23 sheets,
  then was closed. No task-owned documents remained; this task did not close
  owner documents or save model documents. At the final session check the
  drawing was no longer loaded, so no active-sheet change was made.
- Rendered all final pages; reviewed Japanese glyphs and changed sheets at
  readable size. Adjusted only the new dimensions/notes to clear existing
  section letters and views. Raw and workshop PDF text matched, 23 A4 pages.
- Doctor/STEP before and after: unchanged 1,080 models, 1,075 current mirrors,
  four stale and one missing. The two unrelated BoronProbe missing-reference
  findings and affected mirror paths are recorded in the preceding drive-detail
  log. No drawing-related reference blocker or new model staleness was found.
- Gates: 536 tests passed, 7 skipped (91.58 s); Ruff and `git diff --check`
  passed. No published documentation or MkDocs configuration changed.

Manufacturer references consulted: [NTN 51101](https://eshop.ntn-snr.com/en/product/51101-NTN/51101)
and [NTN bearing catalogue, thrust-fit recommendations](https://www.ntnglobal.com/en/products/catalog/pdf/2250E_all.pdf).
The 1.5/7.5 mm mounting explanation comes from this assembly's native geometry,
not a general bearing mounting prescription.

## Remaining decision

Agree the Ø12 journal tolerance with the shop before machining. This pass
clarifies the assembly plan and does not approve h7 or revise the load envelope.
