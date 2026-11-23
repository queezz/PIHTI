# Verify the MonotaRO stage and fit it to the apparatus

## Goal

Review the current MonotaRO stage, copy the apparatus with that stage installed, recheck the rail-to-table hole pattern, and give queezz a complete shopping checklist with verified MonotaRO product links and pack quantities.

## Assembly

- Created `bellows-probe/PIHT-Bellows-probe-monotaro.iam` from the open apparatus under `PIHTI.ipj`. Replaced its stage at the existing vessel-side KF40 datum. Grounded the new stage and the existing KF40 clamp in the copy for the saved review position. All 26 other top-level occurrences retained their transforms. In No-Cage, enabled the existing vessel-side adapter so the connection is visible.
- Reopened the copy using No-Cage. 27 top-level occurrences, 31 healthy relationships and no missing descriptors. The existing and new KF40 adapter faces meet at the same axial position. The probe head extends about 15.1 mm past the KF flange interface toward the vessel. At the saved position Inventor reported zero stage interferences against the vessel adapter, gate valve and KF40 clamp. A travel sweep was outside this view check.
- The two source top-level file hashes matched before and after, and the original apparatus remained open with its unsaved edits. Inventor also saved `sliding-assembly.iam` and `two-section-bellows-on-bearings.iam` during Save Copy As. Their saves were left in place and the two old STEP mirrors are stale. No task-owned Inventor documents remained.

## Rail-hole check

- Native A6061 reference plate measures 1,092 × 215 × 10 mm. Its 36 M6 × 1 through holes match the two installed SBI20 rail envelopes. The rows are 175 mm apart, each 20 mm from its long edge. Each row is 18 on 60 mm pitch and spans 1,020 mm.
- The 1,060 mm rail has 20 mm end-to-hole offsets and the installed rail setback is 27 mm wheel-side and 5 mm vessel-side. The first and last hole centers are 47 and 1,067 mm from the plate wheel end. Shop drawing page 04 and the exact set's MonotaRO/SBC catalogue data agree. Check the delivered rails and small-head screws against the layout before tapping.

## Shopping list

- Updated `bellows-probe/monotaro-basket.md`. All 26 direct product links returned 200 with their matching title, including all seven codes from Pic 3. Quantities include 18 two-screw rail packs, the guide, saddle, plate, support and clamp screws, and the vacuum fasteners.
- Current model has six M6 × 35 bolts and nuts at each of the bypass branch and gauge joints. The selected packs cover the previous 16-piece allowance.
- Outstanding supplier/fit checks are loose-block compatibility with the K1 sets, collar thrust rating, the existing profile series and T-nut fit, and axial shim selection by measured endplay. Exact MonotaRO matches were not found for four class 10 M6 support nuts and four hardened Ø6.6 × Ø18 × 2 mm support washers.

## Verification

- Catalog scan after save found zero Doctor blockers. The automatic STEP mirror exported the checked copy. A later native save made that mirror stale by commit time. Other BoronProbe mirror findings predate this work.
- `git diff --check` and the CAD link/pack checks passed. The notes check still reports the existing missing introductory sentences in the BoronProbe_2026 and Plasma Vessel_2026 READMEs. No software changed.
