# Boron probe inventory note

**Date:** 2026-06-22
**Goal:** Record current Boron Probe / sample holder file locations and the false lead from the Hayashi archive before future integration work.

## Decisions

- Keep the durable inventory in `docs/systems/boron-probe-integration.md` so it is published with the PIHTI engineering docs.
- Keep operational search context in `.agents/2026-06-22-boron-probe-inventory.md` so later agents can see what was searched and what was rejected.
- Treat `\\10.249.254.52\Public\archives\backup\2015-2026\backup_2026\hayashi\backup\3Dprinter\boron_probe_head\sample-holder.stl` as a rejected match: the user identified it as the wrong part, apparently a plasma-box-related part.

## Changed

- `.agents/README.md` - starter convention for PIHTI agent logs.
- `.agents/handoff-template.md` - short copy-paste handoff skeleton.
- `.agents/commit-culture.md` - lightweight PIHTI commit conventions adapted from the articles library.
- `.agents/2026-06-22-boron-probe-inventory.md` - this session log.
- `docs/systems/boron-probe-integration.md` - durable inventory note for current files, rejected external lead, and integration next steps.
- `mkdocs.yml` - added the integration note under Probes & Diagnostics.

## State

- PIHTI git status was clean before edits.
- Current repo Boron Probe Inventor files are already under `BoronProbe/`.
- Generic/sample-holder Inventor files are under `SampleHolder/`, but they are not confirmed as the missing boron probe holder.
- No commit was made.

## Next

- Add the missing holder/source parts into the appropriate repo folder.
- Open the Boron Probe assemblies in Inventor and resolve missing references.
- Update the integration note with confirmed filenames and roles.
- Rebuild docs, then commit deliberately.

## Follow-up: old Hayashi holder

The user clarified that PR #1 / `BoronProbe_2026/` is the new probe design and is not the target.

Search result to keep:

- Desired target: old Hayashi sample/substrate holder.
- Strong archive figure clues: `基板ホルダー.png`, `基板ホルダー組立図.png`, `試料運搬用プローブ.png` under Hayashi's `thesis(master)\修論使用写真・CAD` folder.
- No obvious native Inventor holder source was found in the Hayashi archive by filename; compare against PIHTI `SampleHolder/` and `BoronProbe/HayashiProbeHead.ipt` next.