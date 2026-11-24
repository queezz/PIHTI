# Show installed probe insertion and enable probe rotation

## Installed probe and drawing

- Sheet 02 retains both bench travel views and adds a plan of the installed
  `PIHT-Bellows-probe-monotaro.iam` apparatus with a local axial section through
  the vacuum path. The chamber section shows the tube and identifies the sample
  in the second vessel at the current saved insertion position.
- Replaced the grounded probe occurrence in `monotaro-rear-module.iam` with
  the unlocked insert relationship `Probe rotation at rear flange`. Its offset
  preserves the existing axial position. Made the rear module flexible in
  `sliding-assembly-monotaro.iam` so the rotation reaches the installed assembly.
  Tested 0°, ±90° and 180° at both levels. The sample stayed at the same axial
  coordinate and the surrounding top-level transforms stayed fixed. The
  installed apparatus file retained its pre-existing saved state and edits.

## Title blocks and PDF line weights

- Applied `PIHTI compact` to sheets 02, 03 and 19–22, and replaced the separate
  page-number notes on 19–22 with the title block's live sheet fields.
- The workshop PDF now uses the established stroke map across all 23 pages.
  The separate image objects in shaded views are preserved. Both PDF variants
  retain 14 MonotaRO links, and the original-line-weight export retains the
  native stroke weights. Tooling shipped separately in pihti-dedup 0.37.2.

## Nut-saddle bolts

The two M5 × 45 bolts have 11.5 mm nominal engagement in the 15 mm tapped
rear foot. The measured bolt row is 25.5 mm from the keeper-side housing edge
and 5.5 mm from the edge toward the middle carriage. The documented vacuum
force pulls toward the middle, so this check uses the 5.5 mm tipping arm.
At the upper 0.5 kN vacuum estimate, 15 mm of offset from the contact plane
gives 7.5 N·m and about 1.36 kN total uplift demand in the tipping screen.

At the previously assumed 4 kN preload per screw and a screening friction
coefficient of 0.10, subtracting that uplift from total clamp gives about
0.66 kN of friction resistance, or 1.3 times the estimated normal force.
This depends on achieving preload, usable thread engagement and the joint
faces. The earlier 50 N handwheel case estimated about 3 kN of screw thrust,
which exceeds this friction screen. The two bolts can serve the expected
vacuum load if the assembly assumptions are verified. Jam or end-stop loads
require their own limit or positive shear restraint and a load-path check.

Sources: [17 November hardware review](2026-11-17-bellows-clamps-feet-hardware.md),
[handwheel thrust screen](2026-11-15-bellows-through-bolt-mounts.md), and
[NASA-STD-5020B, appendix A.10](https://standards.nasa.gov/sites/default/files/standards/NASA/B/0/2021-08-06-nasa-std-5020b_final.pdf).
Used the NASA slip method for screening assumptions rather than a qualification
standard for this joint. The measured geometry corrects the earlier long-arm
screen for this direction of load. The saddle drawing and parts were not edited.

## Verification

- The cut passes through the modeled tube and substrate. The installed
  rotation and drawing were checked in invisible copies before publication.
  The final IDW reopened cleanly, including the saved rotary relationship,
  and the task released its background documents.
- Baseline apparatus findings include a suppressed probe-gate descriptor,
  seven legacy driver-lost relationships in the entrance mesh, cathode feed,
  and quartz holder, and features beyond existing stop nodes. The active
  top-level probe gate is a separate resolved occurrence. No new model health
  finding appeared when the drawing added the apparatus views.
- Refreshed the rear, stage and apparatus STEP mirrors. The resulting catalog
  has 1,076 current mirrors, three other stale mirrors and one unrelated
  missing mirror, with zero STEP preflight Doctor blockers.
- Pytest passed all 545 tests and Ruff passed. The native and linked PDF
  checks cover 23 sheets, 375 attached annotations, and 14 product links.
