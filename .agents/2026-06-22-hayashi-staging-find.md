# Hayashi staging find

**Date:** 2026-06-22
**Goal:** Record the location of the old Hayashi sample holder before processing the staged copy.

## Found Path

```text
C:\Users\queez\Dropbox\Drawings\PIHTI\staging\hayashi\PIHTI\BoronProbe\ProbeHead_hayashi\newversion
```

`staging/` is intentionally ignored by git. Treat this folder as source material for review, not as integrated repo content.

## Top-level Contents

Folders:

- `drawings/`
- `OldVersions/`
- `stl/`

Native Inventor files:

- `probe-head.iam` — likely main assembly for the old Hayashi probe head/sample holder.
- `HayashiProbeHead.ipt`
- `sample-holder-base.ipt`
- `sample-cover.ipt`
- `SampleHolder_cover.ipt`
- `Sample.ipt`
- `flange-adapter.ipt`
- `maica_1.ipt`
- `maica_2.ipt`
- `maica_3.ipt`
- `shaft.ipt`
- `washer.ipt`

## State

- Path exists and was minimally inventoried.
- No staged CAD files have been moved, renamed, deleted, or integrated.
- Next step should be duplicate/hash inventory against the tracked PIHTI folders before opening or repairing assemblies.

## Next

- Run `scripts/find_duplicates.py` against this staging folder and relevant tracked roots.
- Compare against `BoronProbe/`, `SampleHolder/`, and relevant `ContentCenter/` parts.
- Only after inventory, decide what to integrate and what to leave in ignored staging.