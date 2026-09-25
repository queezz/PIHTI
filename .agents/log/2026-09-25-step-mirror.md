# STEP mirror (pihti-dedup 0.24.0)

**Goal:** queezz, 2026-09-25: "a local STEP backup, maybe only Dropbox
carries it, lives in the background and is called upon if needed."

## Decisions

- The mirror is the sibling folder `PIHTI-step` beside the workspace
  (override `PIHTI_DEDUP_STEP_MIRROR`), mirroring the tree one to one with
  `<full name>.step` per part and assembly (seven folders hold a part and an
  assembly with the same stem, so the stem alone would collide). Outside the
  workspace so the catalog, the unique-filename search and git never see it;
  Dropbox carries it; a README in its root says it is regenerable. The folder
  is created on first write only; none exists on this machine yet.
- Export recipe proven this morning through the running session:
  `Documents.Open(path, False)`, `SaveAs(<name>.tmp.step, True)`, `Close(True)`,
  move into place. STEP 0.41 s, STL 0.06 s on a 116 KB part; first open 3.8 s.
  Translator option maps are not writable through the bridge and are not
  used. Inventor Server is a dead registration here; `Inventor.Application`
  launches `Inventor.exe /Automation`, so a hidden instance is possible and is
  the explicit `step-mirror sync --launch` switch, untested against a real
  Inventor, never used by the web.
- Background job on the snapshot ticker: only while a session answers (never
  launching), one stale-or-missing file per attempt, oldest first, skipping
  files open in Inventor, 10 s without progress per export, a minute of
  back-off after a failure with that file deferred until it changes, and a
  minute of rest after each export so the owner's Inventor is borrowed only
  briefly while he designs (added at review; `sync` is the fast fill).
  Staleness allows a two-second mtime tolerance for Dropbox-rounded times;
  `.newVer` leftovers are not mirrored.
- Viewer: `/mesh/<path>` builds Inventor files from a current mirror STEP;
  the inspector and part page show "3D needs the STEP mirror · export now"
  (token-guarded, session only) or "Open Inventor to export"; the top bar
  shows "STEP mirror N / M" linking to `/step-mirror`.
- Implementation by an Opus agent; the spacing rule, review, gates and commit
  here.

## Verification

- pytest 410 passed, fresh basetemp; ruff clean; `node --check` clean;
  `git diff --check` clean; strict MkDocs build clean.
- Walk on a scratch copy with a fake session (port 48991, stopped and free):
  one export per tick, open file skipped, both inspector lines, export-now
  with toast, rails at 84 px at every depth, mirror page links 200.

## Risks recorded

- Two machines writing `mirror-index.json` through Dropbox can produce
  conflicted copies; the index is only an accelerator, mtimes remain the
  fallback.
- While an export runs, the rename form's Inventor probe can briefly report
  "did not answer"; they share one session.
- `--launch` needs one real run with Inventor closed before it is trusted.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1 (Opus
  implementation); observed 2026-09-25 JST.
