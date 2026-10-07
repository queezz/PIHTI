# Tidy working tree — 2026-10-08

Goal: commit independent finished work without discarding or editing human content.

Commits: aec8b27 (vessel/probe simulation CAD and data), d3d378c (shared library CAD), 2a63a05 (Doctor disposition), 29c5202 (session evidence).

Verification: 511 pytest tests passed in 47.01s using the declared pihti-dedup interpreter and a fresh external basetemp; Ruff and whitespace checks passed. Read-only inventory scanned 1697 files: 35 hash groups, 16 renamed hash groups, 23 same-name/same-size groups, 17 same-name/different-size groups. No published docs changed; MkDocs not applicable. No version bump earned.

Owner correction: renamed bwllows-probe to bellows-probe after read-only referring-filename checks. Only its own four assemblies name the contained CAD files. Filenames unchanged; unique filename resolution applies. Historical logs and ledger preserved. No CAD reference repair or native geometry edit performed.

Remaining blockers:
- Controller CAD and rename ledger: four new v2 Body/Body001 renames remain unsettled; modified controller assemblies share their references. Complete Inventor repair and settle the connected ledger events. Win-GPIO clip assembly also appears in existing unsettled Wide Din Clip events.
- bellows deletions and bellows-probe additions: confirm replacement for deleted bellows/bellows.iam and verify/save referring assemblies for the original folder move. Later sliding logs explicitly left changes unsaved for review; confirm intended saved design. The spelling correction is complete, but does not settle the original design/move.
- Plasma Vessel/pihti-for-simulation-flat.iam.md: notes check reports unchanged baseline summary findings in BoronProbe_2026/README.md and Plasma Vessel_2026/README.md. Resolve through authorized content correction and rerun notes gate; human text untouched.

Every remaining path is covered by one of those three concrete blockers. Final porcelain follows. No missing guidance, restore, reset, clean, stash, push, tag or ignored-file staging. Scratch retained as verification evidence.

Usage: OpenAI / GPT-6; direct bounded cleanup, no design or child agents; configured model retained despite snapshot lower-tier suggestion; provider usage unavailable.

Final git status --porcelain=v1 -uall:
 M .agents/rename-ledger.jsonl
 D ElectronicsBox/TempController-v2/PlugRecepticle-Plug_Case/Body.ipt
 D "ElectronicsBox/TempController-v2/RKC CONTROLLER.ipt"
 D "ElectronicsBox/TempController-v2/SSR Din Rail Mount/Body.ipt"
 M "ElectronicsBox/TempController-v2/SSR Din Rail Mount/SSR Din Rail Mount.iam"
 M ElectronicsBox/TempController-v2/SSR-on-DIN-mount.iam
 M ElectronicsBox/TempController-v2/SSR-on-DIN.iam
 D "ElectronicsBox/TempController-v2/Solid State Relay/Body.ipt"
 D "ElectronicsBox/TempController-v2/Solid State Relay/Body001.ipt"
 M "ElectronicsBox/TempController-v2/Solid State Relay/Solid State Relay.iam"
 M ElectronicsBox/TempController-v2/TempController-v2.iam
 D ElectronicsBox/TempController/PlugRecepticle-Plug_Case/Body.ipt
 M ElectronicsBox/TempController/PlugRecepticle-Plug_Case/PlugRecepticle-Plug_Case.iam
 D ElectronicsBox/TempController/RT-65D-Bracket.ipt
 D "ElectronicsBox/TempController/SSR Din Rail Mount/Body.ipt"
 M "ElectronicsBox/TempController/SSR Din Rail Mount/SSR Din Rail Mount.iam"
 M ElectronicsBox/TempController/SSR-on-DIN-mount.iam
 D ElectronicsBox/TempController/SSR-on-DIN.iam
 D "ElectronicsBox/TempController/Solid State Relay/Body001.ipt"
 M "ElectronicsBox/TempController/Solid State Relay/Group.iam"
 D "ElectronicsBox/TempController/Solid State Relay/Solid State Relay.iam"
 M ElectronicsBox/TempController/TempController.iam
 M ElectronicsBox/Win-GPIO-Box/cosel-psu-din-clip.iam
 D bellows/README.md
 D bellows/bellows.iam
 D bellows/bellows_1.iam
 D bellows/bellows_2.iam
 D bellows/bellows_bellows.ipt
 D bellows/bellows_flange.ipt
 D bellows/flangeclamp_down.ipt
 D bellows/flangeclamp_up.ipt
 D bellows/linearbearing.ipt
 D bellows/rail.ipt
 D bellows/sourcing/attachments/20260925-184542-image.png
 D bellows/sourcing/attachments/20260925-184612-image.png
 D bellows/sourcing/attachments/20260925-184622-image.png
 D bellows/sourcing/attachments/20260925-185052-image.png
 D bellows/sourcing/movable-probe-rails.md
 D bellows/sourcing/probe-rails.md
?? "ElectronicsBox/TempController-v2/PlugRecepticle-Plug_Case/Plug body 110V.ipt"
?? "ElectronicsBox/TempController-v2/RKC CONTROLLER v2.ipt"
?? "ElectronicsBox/TempController-v2/SSR Din Rail Mount/SSR din clip just a copy.ipt"
?? "ElectronicsBox/TempController-v2/Solid State Relay/Body Solid State.ipt"
?? "ElectronicsBox/TempController-v2/Solid State Relay/SSR plate just a copy.ipt"
?? "ElectronicsBox/TempController/PlugRecepticle-Plug_Case/plug body.ipt"
?? "ElectronicsBox/TempController/RT-65D-Bracket TempController.ipt"
?? "ElectronicsBox/TempController/SSR Din Rail Mount/Din Rail SSR clamp body.ipt"
?? "ElectronicsBox/TempController/SSR-on-DIN backup.iam"
?? "ElectronicsBox/TempController/Solid State Relay/SSR plate.ipt"
?? "ElectronicsBox/TempController/Solid State Relay/Solid State Relay backp.iam"
?? "Plasma Vessel/pihti-for-simulation-flat.iam.md"
?? bellows-probe/Al-profile-30x30-L1000.ipt
?? bellows-probe/Al-profile-30x30-L600.ipt
?? bellows-probe/CF114-CF70-zero-length-adappter.ipt
?? bellows-probe/M16-lead-screw.ipt
?? bellows-probe/PIHT-Bellows-probe.iam
?? bellows-probe/PIHT-Bellows-probe.iam.md
?? bellows-probe/README.md
?? bellows-probe/base-plate-for-bellows.ipt
?? bellows-probe/bellows_1.iam
?? bellows-probe/bellows_2.iam
?? bellows-probe/bellows_bellows.ipt
?? bellows-probe/bellows_flange.ipt
?? bellows-probe/clamp-foot.ipt
?? bellows-probe/flange-camp-114.ipt
?? bellows-probe/flangeclamp_down.ipt
?? bellows-probe/flangeclamp_up.ipt
?? bellows-probe/instead-of-bellows.ipt
?? bellows-probe/lead-screw-nut-preview.ipt
?? bellows-probe/linearbearing.ipt
?? "bellows-probe/rail bwllows probe.ipt"
?? bellows-probe/sliding-assembly-1section-long.png
?? bellows-probe/sliding-assembly-1section-short.png
?? bellows-probe/sliding-assembly.iam
?? bellows-probe/sourcing/attachments/20260925-184542-image.png
?? bellows-probe/sourcing/attachments/20260925-184612-image.png
?? bellows-probe/sourcing/attachments/20260925-184622-image.png
?? bellows-probe/sourcing/attachments/20260925-185052-image.png
?? bellows-probe/sourcing/movable-probe-rails.md
?? bellows-probe/sourcing/probe-rails.md
