# Independent simulation geometry — 2026-10-01

## Goal and decisions

Prepare pihti-for-simulation.iam without subassemblies for solid editing and
later simulation STEP export. Created an independent multibody part using
Inventor Derive with separate bodies, then broke the source link. Preserved
all included geometry; no physical simplifications or cuts were inferred.

## Changed

- Plasma Vessel/pihti-for-simulation-multibody.ipt
- This handoff.

## Verification

PIHTI.ipj was active. Source assembly was saved clean with 16 top-level
occurrences and 85 referenced documents; its direct references resolved.
Read-only inventory: 1185 CAD files, 19 repeated-name groups, 12 conflicting
hash groups. Reopened output: 180 bodies, all solid, zero references, saved
clean. Original assembly remained clean. Output left open in Inventor.
Ruff and git diff --check passed. No tool code changed.

## Next

Use part solid tools to cut and simplify this independent copy, then export
STEP. Review body names, materials and electrical roles before simulation;
fasteners and fine mesh remain present. Existing unrelated dirty CAD work
and the untracked source assembly are outside this change.

Repository test gate: 504 passed in 60.18 seconds.
