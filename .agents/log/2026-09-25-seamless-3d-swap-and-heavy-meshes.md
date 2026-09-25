# Seamless 3D swap and heavy meshes (pihti-dedup 0.23.2)

**Goal:** queezz, 2026-09-25: the inspector jumped on STL hover (background
and scale changed at the still-to-3D swap), and heavy STLs never entered 3D.

## Decisions

- The viewport's clear colour is read from the preview box's computed
  background (`--mesh-backdrop`), the initial camera tight-fits the projected
  vertices exactly as the still renderer does, and the first frame renders
  before the canvas is shown. Measured on `boron-dish.stl`: both backdrops
  `rgb(16,24,34)`, silhouettes agree within 1.6 px per side.
- Mesh payload is positions only; flat normals come from screen-space
  derivatives in the shader (fallback `?normals=1` payload when the extension
  is missing). Format version bumped so old caches rebuild. Cap raised from
  400,000 to 2,000,000 triangles. `enclosure-temp-conroller.stl` (648,220
  triangles, 22 MB payload) reaches its first frame in about 270 ms; a quiet
  "Loading 3D · N MB" line shows above 5 MB.
- Implementation by a Sonnet agent; review, README cap sentence, gates and
  commit here.

## Verification

- pytest 380 passed, fresh basetemp; ruff clean; `node --check` clean on both
  scripts; `git diff --check` clean; strict MkDocs build clean. Scratch port
  48932 stopped and free.

## Owner question answered, not built

- `.ipt`/`.iam` to STEP or mesh on the site: feasible only through Inventor's
  own translators in the running session (the route the rename repair uses);
  nothing outside Autodesk reads the formats and Apprentice cannot export.
  Design: on-demand STL export into the machine-local cache for the viewport,
  explicit STEP export for sharing, batch warm-up while Inventor is open,
  and a ten-minute probe of `InventorServer.exe` to see whether a closed
  Inventor can still convert. Waiting for the owner's go.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1
  (Sonnet); observed 2026-09-25 JST.
