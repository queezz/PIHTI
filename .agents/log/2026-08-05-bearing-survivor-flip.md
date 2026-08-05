# Bearing survivor flip and quarantine relocation

Date: 2026-08-05
Agent: fable

## What

- Audited survivor direction of all 41 applied quarantine groups using the embedded UTF-16 authored self-paths in the CAD files plus a where-used scan of every `.iam`/`.idw`.
- Result: 39/41 correct (the `Plasma Vessel_2026/` snapshots collapsing onto the canonical `Plasma Vessel/` trees), 2 backwards — both BoronProbe bearing parts.
- Flipped the two backwards groups: restored `BoronProbe_2026/parts/B_probe_bearing.ipt` and `B_probe_bearing_without_holes.ipt` (authored originals; referrers include the BoronProbe top-level assemblies and the part's own drawing `parts/図面/B_probe_bearing.idw`), and quarantined the byte-identical Pack-and-Go copies from `Plasma Vessel_2026/contents/` instead. A `flip-note.md` was added to each affected quarantine run; `manifest.json` files record the original operation and were left untouched.
- Moved the quarantine store out of the Inventor workspace: `.pihti-dedup/` → `../PIHTI-quarantine/` (sibling of the repo). With `UsingUniqueFilenames = Yes` and workspace `.`, Inventor filename search could previously resolve into quarantined copies.

## Why

The merge-cleanup survivor rule ("the path this merge added loses") has no concept of canonical location. The embedded self-paths and referrer counts identify the authored home; with the flip, filename re-resolution lands every referrer on `BoronProbe_2026/parts/`.

## Follow-ups

- `pihti-dedup` should write its quarantine outside the workspace by default (v0.3).
- PR #3 exact-duplicate pairs: dry-run plan prepared separately; not applied.
- Leprecon-rooted self-paths in older parts are historical — PIHTI is the renamed successor of the defunct Leprecon project — not a provenance concern.
