# Correct simulation assembly structure — 2026-10-01

## Goal and decision

Owner rejected the multibody part: requires a plain assembly whose bolts and
other components can be deleted normally. Created a new flat IAM directly
from the original assembly's leaf occurrences, not from derived bodies.

## Changed

- Plasma Vessel/pihti-for-simulation-flat.iam
- This handoff.

## Verification

Correct PIHTI.ipj active. Reopened output has 180 top-level part occurrences,
zero subassemblies and zero constraints. Every resolved part path and all 16
transformation matrix entries match the original leaf occurrence within
1e-8. Components are grounded and preserve visibility. Source remains clean.
Deleted M4x8-SHCS:17 in a transaction: count dropped to 179; aborted the
transaction and confirmed 180 restored. Reopened saved file and left it active.
Prior same-session gates: 504 tests and Ruff passed; no tooling changed.

## Next and limitations

Owner can remove individual components and add assembly-level cuts before
STEP export. Parts still reference the original IPT files: part-level edits
would change shared hardware; use assembly cuts or a separate part copy.
Earlier multibody output remains available but is superseded for this task.
No bolts were removed permanently. Unrelated dirty CAD remains untouched.
