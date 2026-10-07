# Complete missing dependencies in BoronProbe_2026 (PRs #1 and #3)

Suggested recipient: @nobuya0829, the recorded submission Git author.

Native Inventor checks in the receiving checkout found five dependencies that
are absent from the submitted merge trees and available Git filename history.
Please supply the original files and their dependencies, or explain and fix an
intended rename/replacement in Inventor.

## Requested files

- [ ] ICF70FLMG4MBA.ipt — referenced by BoronProbe_2026/parts/C70TCK2MBGA.iam
- [ ] WTCK2MB.iam, including its dependent parts — referenced by BoronProbe_2026/parts/C70TCK2MBGA.iam
- [ ] ICF70F 1個付き 19穴.ipt — referenced by BoronProbe_2026/parts/C25K22A4CU.iam
- [ ] W5K22A4CU.iam, including its dependent parts — referenced by BoronProbe_2026/parts/C25K22A4CU.iam
- [ ] ICF70-34-hole.ipt — referenced by BoronProbe_2026/BoronProbe_2026_non-bellows.iam

## Drawing link corrections

- [ ] Explain and repair the intended links in BoronProbe_2026/BoronProbe_5_disassembled.idw:
  it still names BoronProbe_5.iam and BoronProbe_5_disassembled.iam.
  Commit a0c5bbe replaced/renamed those assemblies while moving the drawing.
  The exploded assembly is now BoronProbe_2026/BoronProbe_2026_exploded.iam;
  verify the intended main assembly rather than substituting one by appearance.

## Delivery and verification

Please provide a corrective PR or attach a Pack-and-Go ZIP, with a list of reused
shared components and external libraries. Do not include OldVersions, caches,
locks, vendor Design Data or Templates. Reopen saved assemblies and drawings with
PIHTI.ipj active, run Check-PIHTI-Submission.cmd in your own checkout, and attach
its report. We will verify the resulting references in the receiving checkout
before closing this request.

The six WTCK2MB member-name warnings are not six independently verified missing
direct references; delivering the WTCK2MB assembly's full dependency package
resolves that uncertainty. Staging-only and old OLED warnings are excluded.
The UFC-152 failures followed later archive cleanup and are not assigned to this
submission request.

This is a prepared issue draft, not a posted notification.
