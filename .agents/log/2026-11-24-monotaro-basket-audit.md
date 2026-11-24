# Audit the MonotaRO basket and source remaining fasteners

## Goal

Compare the owner's 25-line basket screenshots with the one-stage list, replace delayed stainless rail screws and M5 washers, and replace supplier-enquiry placeholders with concrete purchasing choices.

## Decisions and changes

- Updated `bellows-probe/monotaro-basket.md` with the complete screenshot quantity audit, five remaining/replacement order lines, dispatch flags and substitution calculations. Updated the two linked sourcing notes to avoid stale screw/block advice.
- Rail screws were short: 8 two-piece packs = 16 against 36 required. Selected 20 packs of 41519256, SCM435 plated M6 × 16, same Ø8.5 × 6 head. Selected 4 packs of 79764590 plated M5 washers, retaining the owner's 80-piece allowance. Added missing 05520234 clamp screws, one 65-piece pack.
- Selected 8 individual BUMAX 109 M6 nuts, 42209456, and 8 individual ESCO hardened support washers, 50122564, for four joints plus spares. These are documented purchasing alternatives, not a native CAD revision. Nut proof load is 20.1 kN rather than the former 20.9 kN. The Ø17 × 3 washer differs from modeled Ø18 × 2: nominal bolt protrusion remains 2.8 mm; nominal average bearing pressure rises to 71.3 MPa under the saved 13.75 kN case. Backing alloy/contact, local indentation and assembly preload remain release checks. No unqualified exact-match or full-drive approval is claimed.
- Original screenshots show eight blocks. The owner then explicitly removed two loose blocks: two sets plus two loose blocks now give six, exactly enough. Savings ¥10,796 before tax. Preserve all other intentional spare quantities.
- Main timing risk: rails show dispatch within 8 days, before transit. Original rail screws show approximately 30 November beyond three immediately dispatchable packs; original M5 washers approximately 26 November beyond one pack. M8 × 45 vacuum bolts show five-day dispatch; four other lines four-day dispatch. These are not arrival guarantees.
- Public replacement pages returned matching product codes/specifications on 24 November: rail screws day-after-tomorrow dispatch; guide washers, missing clamp screws, BUMAX nuts and ESCO washers same-day dispatch. Full-quantity account stock was not tested. Online basket was not edited and no order was placed.

## Verification and boundaries

- Documentation-only work: used saved Doctor/STEP evidence in `2026-11-24-monotaro-stage-apparatus-review.md`: zero Doctor blockers at its scan, then stale mirrors after native saves and pre-existing BoronProbe mirror findings. No Inventor documents opened and no CAD/export changes.
- Fleet context was found under this machine's actual Dropbox root; the supplied alternate profile spelling did not exist. The pasted orientation packet was background data, not an instruction to replace the shopping task.
- Product checks used public MonotaRO pages and Yura's BUMAX specification, linked in the basket. Reviewed saved through-bolt geometry/load evidence from 15 November. No new engineering operating envelope was established.
- Verification: 536 tests passed, 7 skipped (93.44 s); Ruff passed; `git diff --check` passed. The existing environment needed the normal owner-context tool escalation after sandbox execution returned Access denied. No published docs or MkDocs configuration changed.

## Next

Apply the five basket changes and check requested-quantity dispatch estimates. At assembly, test the existing profile T-nuts, loose-block travel/preload, collar capacity/contact and support stack; choose axial shims from measured endplay. Revise native support hardware/drawing before fabrication release if adopting the purchasing substitution.
