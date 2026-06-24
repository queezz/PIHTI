# Boron Probe Integration Inventory

This note records where the current Boron Probe and sample-holder-related files live before the missing parts are added and integrated.

## Current Boron Probe Files

Source folder: `BoronProbe/`

Assemblies:

- `BoronProbe/BoronProbe.iam`
- `BoronProbe/BoronProbeHead.iam`
- `BoronProbe/BoronProbePipe.iam`
- `BoronProbe/BoronHead.iam`
- `BoronProbe/palp-boron-hybrid.iam`

Parts:

- `BoronProbe/BoronProbe-flange.ipt`
- `BoronProbe/BoronProbePipeLong.ipt`
- `BoronProbe/flange-adapter.ipt`
- `BoronProbe/GlassPort-idea.ipt`
- `BoronProbe/HayashiProbeHead.ipt`
- `BoronProbe/SampleTray.ipt`
- `BoronProbe/Shaft.ipt`
- `BoronProbe/SteelSample.ipt`

## Possibly Related Holder Files

Source folder: `SampleHolder/`

- `SampleHolder/Box-with-snaps.iam`
- `SampleHolder/RamanSampleHolder.ipt`
- `SampleHolder/SampleCell.ipt`
- `SampleHolder/SampleCell-mimi.ipt`
- `SampleHolder/SampleHolderBand.ipt`

These are present in the PIHTI repo, but they are not yet confirmed as the missing Boron Probe sample-holder parts.


## Old Hayashi Holder Search

The desired target is the old Hayashi sample/substrate holder, not the 2026 PR design.

Archive clues found in Hayashi's backup:

```text
\\10.249.254.52\Public\archives\backup\2015-2026\backup_2026\hayashi\thesis(master)\修論使用写真・CAD\基板ホルダー.png
\\10.249.254.52\Public\archives\backup\2015-2026\backup_2026\hayashi\thesis(master)\修論使用写真・CAD\基板ホルダー組立図.png
\\10.249.254.52\Public\archives\backup\2015-2026\backup_2026\hayashi\thesis(master)\修論使用写真・CAD\試料運搬用プローブ.png
```

These appear to document the old holder/probe concept. A filename search of the Hayashi archive did not find obvious native Inventor source files named around `sample holder`, `基板ホルダー`, `試料`, or `ホルダ`; only images/STL exports surfaced.

Closest native PIHTI files to compare against:

```text
BoronProbe/HayashiProbeHead.ipt
SampleHolder/Box-with-snaps.iam
SampleHolder/RamanSampleHolder.ipt
SampleHolder/SampleCell.ipt
SampleHolder/SampleCell-mimi.ipt
SampleHolder/SampleHolderBand.ipt
```

Do not use GitHub PR #1 / `BoronProbe_2026/` as the source for this task. That PR is a newer probe design, not the old Hayashi holder being searched for here.


## Found Hayashi Staging Source

The old Hayashi sample holder/probe-head source has been found in ignored staging:

```text
C:\Users\queez\Dropbox\Drawings\PIHTI\staging\hayashi\PIHTI\BoronProbe\ProbeHead_hayashi\newversion
```

Likely key files:

- `probe-head.iam`
- `HayashiProbeHead.ipt`
- `sample-holder-base.ipt`
- `sample-cover.ipt`
- `SampleHolder_cover.ipt`
- `Sample.ipt`

Do not process this staged copy until duplicate/hash inventory is run against tracked PIHTI folders.

## Rejected External Lead

The Hayashi archive search found this STL:

```text
\\10.249.254.52\Public\archives\backup\2015-2026\backup_2026\hayashi\backup\3Dprinter\boron_probe_head\sample-holder.stl
```

Do not treat this as the target Boron Probe sample holder. It was identified as the wrong part, likely from a plasma box / 3D-printing context.

Other nearby exported files from that search:

```text
\\10.249.254.52\Public\archives\backup\2015-2026\backup_2026\hayashi\backup\3Dprinter\boron_powder_base\base_顕微ラマン.stl
\\10.249.254.52\Public\archives\backup\2015-2026\backup_2026\hayashi\backup\3Dprinter\boron_powder_base\boron_powder_base.stl
\\10.249.254.52\Public\archives\backup\2015-2026\backup_2026\hayashi\backup\3Dprinter\optics_supporting\sample_support.stl
\\10.249.254.52\Public\archives\backup\2015-2026\backup_2026\hayashi\backup\3Dprinter\optics_supporting\sample_support_2.stl
```

## Integration Plan

1. Add the missing holder/source parts to the repo when they are found.
2. Prefer native Inventor source files (`.ipt`, `.iam`, drawings) over STL-only exports when possible.
3. Open `BoronProbe/BoronProbe.iam`, `BoronProbe/BoronProbeHead.iam`, and `BoronProbe/BoronHead.iam` in Inventor and resolve references against the added files.
4. Update this note with the confirmed file roles once the assembly opens cleanly.
5. Regenerate folder READMEs if needed with `scripts/generate_readmes.py` instead of editing generated README files by hand.
6. Build the docs and commit the complete integration as one deliberate change.
