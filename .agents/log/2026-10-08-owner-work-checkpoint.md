# Commit the owner's remaining work from today

## Goal

Commit the owner's saved CAD, review records, images and simulation metadata
from 2026-10-08. Earlier agent changes from today already have their own commits.

## Scope and decisions

- Record the gate-valve renames and updated 2026 vessel references in a
  separate commit from the remaining CAD design checkpoint.
- Include the rename ledger unchanged, including the staging-only Hayashi
  rename and the two gate-valve entries still marked unsettled. Do not claim
  native verification that did not complete.
- Include Boron probe and vessel edits, the Mizuno probe head and pipe parts,
  bellows/clamp/adapter edits, long/short assembly PNGs, Doctor deferral and
  the substrate colour entry in simulation/parts.json.
- Commit the saved on-disk state. Inventor was unavailable through its active
  COM object and no Inventor process was listed; no CAD was opened or rewritten.
- Keep ignored staging, save history, caches and the STEP mirror excluded.

## Verification

- Read-only duplicate inventory: 1744 files; 35 hash duplicate groups,
  16 renamed hash groups, 23 same-name/same-size groups and 16
  same-name/different-size groups. No cleanup was performed.
- The renamed CF150 gate-valve body is byte-identical to its former tracked
  path. The renamed assembly contains CF150-gatevalve-body.ipt; all three
  changed 2026 vessel assemblies contain CF150-gatevalve-assembly.iam.
- The read-only embedded-reference scan found no remaining curated assembly
  or drawing naming gate_valve.ipt or gate_valve_assembly.iam. This is filename
  evidence, not a substitute for native Inventor resolution verification.
- Doctor, rename-ledger and simulation JSON parsed successfully.
- Ruff and git diff --check passed.
- Full pytest: 525 passed in 42.36 seconds using a fresh machine-local
  temporary directory after the normal basetemp failed with Windows
  permission errors.

## Next

The two gate-valve ledger entries still need native verification through
Inventor. The Doctor deferral records the missing ICF70-34-hole.ipt in
BoronProbe_2026_non-bellows.iam. Preserve these explicit pending records.
Local commits only; no push.
