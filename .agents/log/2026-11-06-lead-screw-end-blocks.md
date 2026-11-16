# Lead-screw end blocks and handwheel concept

**Date:** 2026-11-06
**Goal:** Sketch the lead-screw stops and wheel directly in the running Inventor assembly.

## Decisions
- Owner simplified the proposal to two opposed, uncovered bearing seats. One shared block part is installed twice, pockets facing inward. Existing screw shoulders and opposed outer-ring stops retain the shaft; no covers or shaft collars.
- Measured shaft centre 30 mm above plate, end journals diameter 12 mm, bearings 12 x 28 x 8 mm. Block 60 x 20 x 50 mm; seat diameter 28 mm by 8 mm, outboard shaft opening 18 mm. Two 6.6 mm vertical mounting holes at 46 mm spacing, with 11 x 6 mm head recesses.
- Each stop face is nominally 0.02 mm outboard of its bearing face, leaving 0.04 mm total geometric axial clearance. This clears the imported outer-ring detail and avoids imposing nominal preload. This is a concept position, not a validated tolerance specification.
- Wheel diameter 50 mm, disc 6 mm, split hub diameter 26 x 20 mm with diameter 12 mm bore. Nominal wheel-to-plate clearance is 5 mm. Grip diameter 9 x 30 mm at 18 mm crank radius.

## Changed
- bellows-probe/lead-screw-end-block.ipt: five healthy native extrude features; two instances.
- bellows-probe/lead-screw-handwheel.ipt: seven native features, split hub, M4 clearance/pilot halves and grip mounting hole.
- bellows-probe/lead-screw-handwheel-grip.ipt: hollow grip concept.
- bellows-probe/sliding-assembly.iam: four occurrences and twelve origin-plane constraints added; saved. Left a close native view on the wheel end.
- This handoff. No commits or pushes.

## State and verification
- Verified PIHTI.ipj active before native work. Initial assembly was clean in Inventor but its disk file already had owner Git modifications. Existing dirty Git paths and untracked bearing import were preserved.
- Read-only inventory: 1246 CAD files, 20 repeated-name groups, 13 different-hash name collisions, 7 same-name exact-copy groups, 14 different-name exact-copy groups. No cleanup or imports performed.
- All 83 pre-existing occurrence transforms and grounding checked against baseline before assembly save. Final 87 occurrences, 36 healthy constraints, 75 healthy active joints and one pre-existing suppressed joint. New part features healthy; saved references resolved.
- Transient solid intersections checked for all bounding-box candidate pairs involving new parts: zero positive volume. Use explicitly transformed native bodies: copying an occurrence SurfaceBody proxy drops its placement. For flexible assemblies recurse through current SubOccurrences, not Definition.Occurrences; source poses differ. Unrelated source-pose and untransformed-body trials gave false collisions and were replaced by the actual instance checks.
- Native close view visually inspected. Reusable part file names checked for uniqueness. git diff --check passed; no runtime code changed, so software test suite not rerun.
- Pre-edit assembly backup, scripts, pose baseline, intersection checks and native inspection image retained in this chat's external task directory; not portable repository paths.

## Next
- Review the native concept with owner before fabrication. Plate drilling/tapping was not changed, mounting bolts not modeled. Hub M4 tap pilot needs thread specification; clamp screw and grip fastener/nut are not modeled. Grip currently constrained rigidly for layout.
- Confirm axial load, endplay/tolerance stack, bearing seat fits, mounting fasteners and strength. Static concept checks do not certify load capacity or full-travel clearance.
