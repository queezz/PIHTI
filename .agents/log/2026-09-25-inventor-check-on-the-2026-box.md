# Inventor automation check on the second box (Inventor 2026)

**Date:** 2026-09-25
**Goal:** queezz, live: "test if Inventor automation works on this BOX". Ran
`.agents/campus-pc-check.md` on the second Windows workstation, which turned
out to run Inventor 2026 (Build 300175050, no update), not the 2027 the
handout expected. Nothing in CAD or in the STEP mirror was changed.

## Decisions

- The box is not the campus PC the handout describes: `lab pihti` exists and
  was already serving 0.27.1 on 4185, and `fleet`, `lab helm` and `pihti-log`
  run here. The handout's steps still apply and were followed in order.
- Step 5 (`step-mirror export ... --force`) was refused by this session's
  permission gate because `--force` overwrites a mirror file. The same code
  path, `inventor_session.export_copy`, was run instead with a scratch target
  outside Dropbox, so the mirror's `bellows/rail.step` is untouched.
- Step 6's failure was diagnosed, not worked around: a second, read-only open
  of `bellows.iam` through `OpenWithOptions(SkipAllUnresolvedFiles)` to read
  Inventor's `ErrorManager` messages. That call raised Inventor's
  "saved in a newer version" prompt and timed out at the worker; the plain
  `Open` before it raised a COM exception without a prompt.
- The prompt is still open in Inventor (a dialog-class window titled
  "Autodesk Inventor Professional" with OK / Close / Cancel / Accept). Pressing
  Close for the owner was refused by the session's permission gate, so it is
  left for queezz: one click on Close. COM probes answered normally with it up.

## Changed

- `.agents/directions.md` - new item, Inventor versions across machines.
- `.agents/campus-pc-check.md` - step 6 now says what a 2026 box prints.
- The venv `~/.venvs/pihti-dedup` (outside Dropbox): it carried an editable
  install stamped 0.13.0 and no `comtypes`; reinstalled with
  `.[dev,preview,step,inventor]`, now 0.27.1 + comtypes 1.4.17 on Python
  3.14.5. The live viewer picked comtypes up without a restart, because the
  session module imports it at call time.

## State

| Step | Result |
|---|---|
| 1 install | `Successfully installed comtypes-1.4.17 pihti-dedup-0.27.1` |
| 2 pytest | 485 passed in 72 s, fresh basetemp |
| 4 status | 905 current / 0 stale / 3 missing / 3 need Doctor (same three as the main workstation); `connect()` reports Inventor 2026, active project `PIHTI.ipj`, unique filenames on, workspace `.`, no documents open; `Documents.OpenWithOptions` and `TransientObjects.CreateNameValueMap` both present |
| 5 export | `export_copy(bellows/rail.ipt -> scratch)` = `exported` in 5.6 s, 14.8 kB ISO-10303-21 file, no dialog, no leftover document |
| 6 dry run | `bellows\bellows.iam: cannot open: (-2147352567, 'Exception occurred.')`; `ErrorManager`: "This file was saved in a newer version of the product ... bellows.iam (Inventor 2027.1 (Build 311270010, 270A))"; `DRY RUN: nothing renamed or saved`; `rail.ipt` in place |

So the automation itself works on this box: COM attach, version, project,
open documents, invisible open, STEP `SaveAs` copy, close, and the plan
step all reached Inventor. What does not work is opening any file the 2027
machine has saved. A scan of `last_updated_with` across all 915 `.ipt`/`.iam`
in the workspace found six such files (listed in the directions item); the
rest were saved by 2026 or older and open here.

Not verified here: the batch export and Stop from the STEP mirror page, and
Fix in Inventor on the Wide Din Clip referrers, which need a real dialog-free
open on files this box can read (`TempController.iam` and
`cosel-psu-din-clip.iam` were saved by 2026, so they are candidates).

## Next

- queezz: close the newer-version prompt in Inventor (Close).
- queezz: decide the Inventor version question in `directions.md`; until
  then run Doctor fixes and mirror exports for the six 2027 files on the 2027
  machine only.
- The handout's step 5 line can be reproduced on this box by queezz himself
  from a PowerShell prompt; nothing in the tool blocked it.

## Second run, Inventor 2027.1 (same evening)

queezz started Inventor 2027.1 on this box, then uninstalled the older
Inventors (owner decision 2026-09-25: this box runs 2027 only, so the
directions item on Inventor versions across machines is withdrawn as settled).
He had `bellows.iam` and its parts open, `rail.ipt` among them.

| Check | Result |
|---|---|
| detection | `connect()` 2027.1 (Build 311270010, 270A), `PIHTI.ipj` active, unique filenames on, 11 owner documents open |
| step 6 on rail.ipt | refused, as designed: `blocked: rail.ipt is open in Inventor: close it first`; `DRY RUN: nothing renamed or saved` |
| step 6 on an unopened part | `BoronProbe/flange-adapter.ipt` -> `BoronProbe/BoronHead.iam: will repoint 1 reference`; dry run, file untouched |
| export, 2027-saved file | `UFC-152.ipt` -> `exported` in 0.36 s to a short temp folder |
| export, 2026-saved file | `CF-70-Tee.ipt` -> 370 kB STEP, also `.stp`; `SaveAs` copies to every length up to 259 characters wrote a file |
| open documents after | still the owner's 11, nothing of ours left open |

One false alarm on the way: `export_copy` into this session's scratch folder
reported `failed: Inventor wrote no file` with no `ErrorManager` message. The
scratch folder is 245 characters deep, so the temporary name pushed the
target past the Windows 260-character path limit (259 wrote, 262 did not).
The mirror's longest temporary path is 228 characters, so the tool is not
affected; a target beyond 260 fails silently in Inventor, which is worth
knowing if the mirror ever moves somewhere deeper. The STEP translator
add-in is registered and active on 2027.

Seen and left alone: the worktree carried the owner's own `bellows/bellows_1.iam`
modification and an untracked `bellows/sourcing/` folder from his live
session. Temp folders made for the length test were removed.

Still not run, both save real files: the batch export and Stop from the STEP
mirror page, and Fix in Inventor on the Wide Din Clip referrers.
