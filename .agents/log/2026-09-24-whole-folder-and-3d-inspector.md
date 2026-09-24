# Whole-folder view and 3D inspector (pihti-dedup 0.23.0)

**Goal:** queezz, 2026-09-24: "Can we do the inspector 3D rotate/interact
with STLs? Also the show 48 more... maybe we can just show?"

## Decisions

- Folder pages render every direct file (largest today: 172) with lazy image
  loading; the 48 cap stays only for archive-wide search, where "Show 48
  more" now lands on the first new tile. Server time on `3D-printing` went
  from 7 ms for 48 tiles to 22 ms for 172.
- `GET /mesh/<path>?v=` serves a compact binary (positions and flat normals)
  built by the same loader the preview renderer uses, cached under
  `.pihti-dedup/meshes/`, versioned and immutable like previews, capped at
  400,000 triangles (three workspace files exceed it and keep the still
  image). `warm-previews --meshes` prebuilds: 243 files in 71 s.
- The viewport is plain WebGL in `static/viewer3d.js` (357 lines): fit to
  the bounding box, isometric start matching the stills, drag orbits, wheel
  zooms to the pointer, right- or shift-drag pans, double-click refits, flat
  shading on the Inventor light-blue backdrop; still image until the mesh
  arrives and as the fallback; one fetch per settled file, buffers freed on
  switch; no inertia under reduced motion. No library was downloaded: none
  was needed and the owner's rules keep dependencies out.
- Implementation by an Opus agent; review, gates and commit here.

## Verification

- pytest 370 passed, fresh basetemp; ruff clean; `node --check` clean on
  both scripts; `git diff --check` clean; strict MkDocs build clean.
- Browser walk on a scratch copy (port 48974, stopped and port-checked): orbit
  and zoom with the real mouse, pan with synthetic drags, fetch discipline
  across 20 hovered tiles, rails fixed at every depth, 370 links 200.
- The agent's timing run created a 280 MB mesh cache inside `.pihti-dedup/`
  and deleted it again; the workspace holds no mesh cache.

## Open, going into 0.23.1

- At 1920×900 the left rail leaves the inspector no room for a preview, so
  the 3D view only appears on windows about 1000 px tall or more, and then
  at 383×127. The rail needs slimming: the Legend as one compact badge row,
  the note budget smaller, inspector preview given a real minimum.
- The mesh cache belongs outside Dropbox (fleet RULES.md §8/§12): move
  `.pihti-dedup/meshes/` (and the preview cache) to machine-local storage
  under `%LOCALAPPDATA%` with an environment override.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1 (Opus
  implementation); observed 2026-09-24 JST.
