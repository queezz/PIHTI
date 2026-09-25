# Sync past timeouts and fine STEP tessellation (pihti-dedup 0.24.2)

**Goal:** the first real `step-mirror sync` stopped after 351 files when
`TempController.iam` raised Inventor's Resolve Link dialog (its August
`Wide Din Clip` rename, still unsettled) and timed out; 556 files were never
started. And a student's STEP looked low-polygon in the viewport.

## Decisions

- After a timeout the batch probes the session once; if Inventor answers the
  batch continues and the file stays "timeout" for that run (no second
  attempt); if not, it stops with "Inventor is not answering (a dialog may be
  open) · N not started", exit 1. Failures are listed by path at the end.
- The viewport tessellates STEP at `tol_linear=0.01, tol_angular=0.15`
  (434k triangles instead of 64k on `BoronProbe_5.stp`, 1.4 s instead of
  0.8 s); the 128 px stills keep the coarse setting; mesh format version 3
  rebuilds the cache on next view. The student's export was fine.
- Sync fix by a Sonnet agent; tessellation, review, gates and commit here.

## Verification

- pytest 418 passed, fresh basetemp; ruff clean; `git diff --check` clean.
- Owner action still open: open `TempController.iam` normally, resolve to
  `Wide Din Clip V1.ipt`, save, tick Settled on Renames (three entries).

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1
  (Sonnet); observed 2026-09-25 JST.
