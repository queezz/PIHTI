# Duplicate Deletion Candidates

**Date:** 2026-06-22
**Status:** Marked for review only. Nothing deleted.

## Summary

After PR #1 merged, `Plasma Vessel_2026/` contains many files already tracked under `Plasma Vessel/`.

Classification from hash/name checks:

- `Plasma Vessel_2026/`: 57 files total.
- 42 files are exact SHA-256 duplicates of files already under `Plasma Vessel/`.
- 4 files share names with existing files but differ in content.
- 11 files had no obvious old match by filename/hash.

## Candidate Delete Groups After Reference Check

These `Plasma Vessel_2026/` subtrees are mostly or entirely byte-for-byte duplicates of existing `Plasma Vessel/` subtrees and should be considered deletion candidates after Inventor references are checked:

```text
Plasma Vessel_2026\Cathode-Anode-Flange\
Plasma Vessel_2026\Cathode-Anode-Flange\copper-feed\
Plasma Vessel_2026\Plasma-Flange-2024\
Plasma Vessel_2026\Plasma-Flange-2024\feeds\
```

Canonical existing locations:

```text
Plasma Vessel\Cathode-Anode-Flange\
Plasma Vessel\Cathode-Anode-Flange\copper-feed\
Plasma Vessel\Plasma-Flange-2024\
Plasma Vessel\Plasma-Flange-2024\feeds\
```

## Same Name, Different Content: Review, Do Not Delete Blindly

```text
Plasma Vessel_2026\contents\CF-70-Tee.ipt
  vs ContentCenter\CF-parts\CF-70-Tee.ipt

Plasma Vessel_2026\contents\ICF70_to_KF40.ipt
  vs ContentCenter\CF-KF-adapters\ICF70_to_KF40.ipt

Plasma Vessel_2026\gate_valve\UFC-152.ipt
  vs Plasma Vessel\Plasma-vacuum-cross\UFC-152.ipt

Plasma Vessel_2026\Plasma-vacuum-vessel\UFC-152.ipt
  vs Plasma Vessel\Plasma-vacuum-cross\UFC-152.ipt
```

## New / No Obvious Old Match

Keep these until the 2026 plasma vessel integration is understood:

```text
Plasma Vessel_2026\contents\CF_114-70.ipt
Plasma Vessel_2026\contents\ICF_114-70.ipt
Plasma Vessel_2026\contents\ICF114FDS63B.stp
Plasma Vessel_2026\contents\ICF114-through.ipt
Plasma Vessel_2026\gate_valve\gate_valve.ipt
Plasma Vessel_2026\gate_valve\gate_valve_assembly.iam
Plasma Vessel_2026\PIHTI-for-Boron_2026.iam
Plasma Vessel_2026\Plasma-vacuum-vessel\Cross-6way-152IC-L205p8.ipt
Plasma Vessel_2026\Plasma-vacuum-vessel\Cross-6way-152IC-L255p8.ipt
Plasma Vessel_2026\Plasma-vacuum-vessel\Plasma-vacuum-vessel-152IC-cross-L205p8.iam
Plasma Vessel_2026\Plasma-vacuum-vessel\Plasma-vacuum-vessel-152IC-cross-L255p8.iam
```