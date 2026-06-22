# Hayashi PIHTI Clone Check

**Date:** 2026-06-22
**Question:** Is `staging/hayashi/PIHTI/` basically an older clone/copy of this PIHTI repo?

## Short Answer

Yes. The staged Hayashi `PIHTI/` tree is very likely an older copy of this repo plus Hayashi-specific working folders.

The duplicate inventory found that most shared folders are byte-for-byte identical to files already tracked in the current repo, usually at the same relative path. The non-matching areas are exactly where older/private Hayashi work appears to live.

## Full-Repo Comparison

Command run:

```bash
python scripts/find_duplicates.py staging/hayashi/PIHTI . --skip-dir staging --markdown .agents/2026-06-22-hayashi-pihti-full-clone-check.md --json .agents/2026-06-22-hayashi-pihti-full-clone-check.json --max-group-lines 500
```

Results:

- Staged files scanned: 572
- Current repo files scanned in comparison: 1395
- Staged files with exact hash match somewhere in current repo: 429 / 572 (75.0%)
- Staged bytes with exact hash match somewhere in current repo: 167,450,591 / 245,724,676 (68.1%)
- Staged files with exact hash match at the same relative path: 407 / 572 (71.2%)
- Staged bytes with exact hash match at the same relative path: 158,207,919 / 245,724,676 (64.4%)
- Same relative path but different hash: 41 files
- No hash match in current repo: 143 files
- No same relative path in current repo: 124 files

## Folder-Level Signal

Very clone-like folders:

- `3D-printing/`: 80 / 84 files hash-match, all 80 at same relative path.
- `ContentCenter/`: 67 / 70 files hash-match, all 67 at same relative path.
- `Documents/`: 25 / 25 files hash-match at same relative path.
- `Drawings-PDFs/`: 10 / 10 files hash-match at same relative path.
- `SampleHolder/`: 5 / 5 files hash-match at same relative path.
- `Scaffolding/`: 8 / 8 files hash-match at same relative path.
- `Plasma Vessel/`: 110 / 134 files hash-match, 107 at same relative path.

Not clone-like / likely Hayashi-specific or older work:

- `BoronProbe/`: only 7 / 84 files hash-match. Most unmatched files are under `ProbeHead_hayashi/`.
- `PALP/`: only 25 / 53 files hash-match, with a staged `LangmuirProbe/` subtree not present in current PIHTI.
- `ElectricAdapters/` and parts of `ElectronicsBox/`: many files hash-match current repo content but are organized under different paths.

## Important Staged-Only Hayashi Work

The old Hayashi sample-holder/probe-head material is staged here:

```text
staging/hayashi/PIHTI/BoronProbe/ProbeHead_hayashi/
```

Especially:

```text
staging/hayashi/PIHTI/BoronProbe/ProbeHead_hayashi/newversion/probe-head.iam
staging/hayashi/PIHTI/BoronProbe/ProbeHead_hayashi/newversion/HayashiProbeHead.ipt
staging/hayashi/PIHTI/BoronProbe/ProbeHead_hayashi/newversion/sample-holder-base.ipt
staging/hayashi/PIHTI/BoronProbe/ProbeHead_hayashi/newversion/sample-cover.ipt
staging/hayashi/PIHTI/BoronProbe/ProbeHead_hayashi/newversion/SampleHolder_cover.ipt
staging/hayashi/PIHTI/BoronProbe/ProbeHead_hayashi/newversion/Sample.ipt
```

There are also older versions under:

```text
staging/hayashi/PIHTI/BoronProbe/ProbeHead_hayashi/oldversion/
staging/hayashi/PIHTI/BoronProbe/ProbeHead_hayashi/oldversion2/
staging/hayashi/PIHTI/BoronProbe/ProbeHead_hayashi/oldversion3/
staging/hayashi/PIHTI/BoronProbe/ProbeHead_hayashi/oldversion4/
```

## Interpretation

Treat `staging/hayashi/PIHTI/` as an old repo clone/copy, not as a separate clean source tree. Most folders should not be imported wholesale. Use the hash inventory to ignore files already present, then selectively inspect Hayashi-specific subtrees such as `BoronProbe/ProbeHead_hayashi/`.

## Follow-up Cleanup

After this clone check, the duplicate staged `staging/hayashi/PIHTI/` tree was removed by the user. Remaining ignored staging is now:

```text
staging/hayashi/SpectroscopySystem/
```

Current quick inventory after cleanup:

- Remaining staged files: 131
- Remaining staged bytes: 80,141,890
- `staging/hayashi/PIHTI/` no longer exists.
- Several `OldVersions/` folders still exist under `SpectroscopySystem/` and can be removed in a separate cleanup pass if desired.