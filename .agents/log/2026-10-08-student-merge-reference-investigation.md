# Student merge reference investigation — 2026-10-08

## Request and scope

Investigate the owner's 13-row Doctor screenshot and incomplete student CAD
submissions. Traced all listed names in available local Git history, PR #1
(328d9ba, 2026-06-14) and PR #3 (2e29170, 2026-08-05), and native Inventor
2027.1 descriptors. The owner identifies this as Mizuno's submission; local
authorship evidence names nobuya0829. No remote/contact operation performed.

## What happened

Git merges tracked blobs, not the external dependency graph inside Inventor.
Five genuine native dependencies of submitted assemblies never occur as files in
available Git history. Four are already absent from PR #1's tree:
ICF70FLMG4MBA.ipt and WTCK2MB.iam in C70TCK2MBGA.iam;
ICF70F 1個付き 19穴.ipt and W5K22A4CU.iam in C25K22A4CU.iam.
PR #3 additionally contains BoronProbe_2026_non-bellows.iam referencing
ICF70-34-hole.ipt with no such file in its tree. These were incomplete submissions,
not files the tidy session deleted. Their native descriptors are missing and
point outside the receiving workspace; machine/student paths are not committed.

The screenshot is not 13 proven missing student parts:

| Screenshot names | Evidence |
| --- | --- |
| ICF70-34-hole.ipt; ICF70FLMG4MBA.ipt; WTCK2MB.iam | Genuine missing direct references, absent in their incoming merge trees and all available Git filename history |
| WTCK2MB_1.ipt through WTCK2MB_6.ipt | Embedded names, no direct descriptors in C70TCK2MBGA.iam; the genuine missing parent is WTCK2MB.iam. The unavailable parent's own dependencies cannot be independently checked |
| BoronProbe_5_disassembled.iam | Student commit a0c5bbe renamed it R100 to BoronProbe_2026_exploded.iam; exploded assembly's old name is a stale string. However, the moved IDW still has a genuinely missing direct descriptor for the old name |
| OLED 2.42 12864 v7.iam | Older ElectronicsBox reference string, no matching native direct descriptor; not attributed to student PR changes |
| ISO 4762 - M4 x 12ISO.ipt; probe-head.iam | Old index leaked ignored staging/hayashi material into Doctor. Not curated submission dependencies |

The moved drawing BoronProbe_5_disassembled.idw also directly misses
BoronProbe_5.iam, deleted in a0c5bbe when the new main assembly was added.
Both drawing links need an intentional Inventor repair or a documented historical
disposition. A PDF survives; preserve it. Do not reconstruct an obsolete assembly
or silently substitute a different revision merely to clear the queue.

Two further student-tree UFC-152 failures have a different cause. The files were
present in BOTH merges. Manual consolidation group 3a70e239a738c9f0 recorded their
removal on 2026-08-06; commit 6df56ca on 2026-08-17 removes them and retains
Plasma Vessel/Plasma-vacuum-cross/UFC-152.ipt. Two assemblies still have missing
native descriptors despite that survivor. The different-revision cleanup did not
settle all references. This is subsequent archive-curation work, not an incomplete
student merge. Repoint only through Inventor against the documented survivor and
verify intended geometry/revision.

## Changes

- Correct reference-index scope: ignored staging cannot contribute active Doctor
  referrers. It stays in filename resolution/collision checks because Inventor
  may still resolve into it. Regression covers that distinction.
- Tool patch 0.31.4 in both version files and changelog.
- Recorded eight exact assembly/name native verifications: the exploded assembly
  old name, the OLED old name and six WTCK2MB member names. No missing direct link
  suppressed, no CAD saved, no global filename exemption.
- Saved portable evidence in submission-reference-audit.json.
- Added submission-intake.md and its orientation pointer. Incoming packages need
  native closure checks for assemblies AND drawings, identified shared components,
  and explicit receiving-workspace verification. Merge is not canonical acceptance.
- Recorded remaining investigation/repair work in directions rather than making
  the owner responsible for speculative geometry replacement.

## Verification and operating state

512 tests passed in 49.24 seconds using the declared pihti-dedup interpreter,
fresh external basetemp and no cacheprovider. Ruff and whitespace checks passed.
Live read-only native recheck confirmed all eight zero-direct-descriptor pairs
and the drawing's two missing links. Index readback has no staging-only referrers
and no verified stale assembly names. The drawing's missing link remains visible
to reference indexing. Doctor's queue is assembly-based and does not substitute
for a native drawing check.

No published docs changed; MkDocs not applicable. No native CAD moved, replaced,
deleted or saved in this investigation. Existing eight clean student drawing
documents remain resident from the prior audit. Owner service was not restarted:
staging scope fix loads on its next normal Lab restart. Verification-ledger changes
use the existing reload path. Detailed source reports/scratch remain external TEMP;
committed evidence removes workstation paths. No push or tag.

Usage: OpenAI / GPT-6; direct investigation, zero child agents; usage unavailable.
