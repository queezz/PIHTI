# 2026-09-25 evening handoff — what landed, what waits for the owner

Orchestrator summary of the afternoon and evening slices (JST). Each slice
has its own log beside this one; this entry is the cold-start map.

## Committed on master today (tooling)

| Version | Commit | What |
|---|---|---|
| 0.25.0 | `45d58d1` | Y up for Inventor files, section plane, Still \| 3D, coarse fallback for a STEP over the triangle cap, WebGL context recovery |
| 0.26.0 | `0acac02` | Export fresh STEPs button on the STEP mirror page, batch thread, Stop, status polling |
| 0.27.0 | `6f96d4c` | One `\|+\|` layout on every page, STEP mirror tab, Doctor rows with Fix in Inventor (dialog-free open), Rename card on the part page, part-number callout removed, copy cut to punch lines |
| 0.27.1 | `f403e75` | Needs-Doctor catches a plainly missing part (template, Content Center and cut-name exemptions) |
| — | `40d1ca2` | `.agents/campus-pc-check.md`, the handout for the second workstation |

Owner's CAD work committed by the agent, content only: `ca2a4cf` fastener
moves and GX12/OLED renames with the ledger, `d506490` 23 main/cover
sidecars, `7e16498` ProbeRest parts and prints.

## The student submission

Branch `merge/BoronProbe-update`, checked out in the git worktree
`~/pihti-merge` (outside Dropbox), four commits above master: the merge of
`origin/BoronProbe-update` (no conflicts), the Pack-and-Go `Design Data`
drop (237 files), the folder rename `SpectroscopySystem_Hayashi/` →
`Hayashi/` (owner's choice), and the review log
`2026-09-25-boronprobe-update-merge-review.md` (on the branch, not master).

Before that branch is checked out in Dropbox:

1. `staging/hayashi/` (98 CAD files, git-ignored, inventory-skipped) is a
   copy of the same submission. Inventor's workspace does not skip it, so
   every `Hayashi/` name would exist twice. Owner deletes or moves it.
2. Inventor open with no documents; then `git worktree remove ~/pihti-merge`
   and `git checkout merge/BoronProbe-update` in Dropbox.
3. Doctor, with Inventor: the seven clashes (`substrate.ipt`,
   `BoronProbe.iam`, `rail.ipt`, `clamp_for_bearing.ipt`, three vendor
   downloads beside edited copies), then the six missing components in two
   new assemblies (the `ICF70SWX` set, `probe-head.iam`, an ISO 4762 M4
   screw) which only the students can supply.

Ledger renames do not touch the submission; the moved fasteners resolve by
unique name.

## Needs the owner at the desk with Inventor (never run remotely)

- 0.26.0 Export fresh STEPs: one real batch, watching the status line; Stop
  during a real export; the background job standing aside.
- 0.27.0 Fix in Inventor on the three Wide Din Clip referrers: that
  `OpenWithOptions(SkipAllUnresolvedFiles)` opens without Resolve Link
  through comtypes, the repoint saves and verifies, the ledger settles.
- 0.27.0 Rename and fix in Inventor on `RKC CONTROLLER.ipt` or `board.ipt`.
- Restart `lab pihti` first; the live process still runs 0.25.0 code.
- The campus PC handout, on the second workstation.

## Open questions recorded in directions.md

TempController vs TempController-v2 (owner), vendor bundle collapse,
git-previews cache location. Four of the five newly blocked assemblies in
0.27.1 exported fine earlier today; their missing names may be Save As
leftovers, and they sit in Doctor for the owner to judge.
