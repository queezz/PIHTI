# Full-window 3D view (pihti-dedup 0.24.3)

**Goal:** queezz, 2026-09-25: "I want an option to maximize/enlarge the
viewer. Just so..."

## Decisions

- A quiet "Enlarge" control at the right end of the inspector's button row
  (visible only while a mesh shows; it cannot sit under the viewport without
  shrinking the preview at the swap) and a line under the part page's view;
  `F` on a focused tile. It opens a native dialog filling the window with
  the same mesh (no second fetch), the file name and folder in the head, the
  same orbit/zoom/pan/refit; Escape, × and the backdrop close it, focus
  returns to the opener, the inspector keeps its own camera, GL resources are
  freed on close. Opened only by the owner's action, so the "nothing floats
  over the grid" rule holds.
- Implementation by an Opus agent; review, gates and commit here.

## Verification

- pytest 421 passed, fresh basetemp; ruff clean; `node --check` clean on
  both scripts; `git diff --check` clean; strict MkDocs build clean.
- Walk on a scratch copy (port 48937, stopped and free): open by F and by
  button, orbit/zoom/pan/refit, resize refit, three ways to close, focus
  return, 27 open/close cycles without WebGL warnings, rails at 84 px.

## Next (owner requests today, going into 0.24.4)

- Skip an assembly whose referenced names are missing or non-unique before
  opening it, so Inventor never raises Resolve Link or Non-Unique Project
  File Names during a mirror export; list it as "needs Doctor".
- Short CLI printout grouped by folder; full paths in `export.log` at the
  mirror root.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1 (Opus
  implementation); observed 2026-09-25 JST.
