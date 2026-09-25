# Y up, section view and Still / 3D (pihti-dedup 0.25.0)

**Goal:** four viewer items from the orchestrator's brief: recover from a
lost WebGL context; show Inventor files Y up at Inventor's Home view; a
section plane; a Still | 3D toggle, all in one quiet mesh-tools line.

## Decisions

- One `mesh_tools()` macro (`_file_tile.html`) renders the line in three
  places: under the inspector's preview (between the preview and the mesh
  note; starts `is-idle`), inside the part page's preview box, and in the
  Enlarge dialog's head before ×. Chips are `copy-path inspector-flag
  mesh-tool` buttons with `aria-pressed`; the section place is a range input.
  No form in the line, so the inspector's form-order test holds. In the
  inspector the line always takes its height (`visibility: hidden` when the
  file has no mesh URL) and `fitImage()` counts it, so the preview never
  changes height; on the part page it is `width: 0; min-width: 100%` so it
  wraps inside the preview's own width instead of widening the column.
- `PihtiMeshTools` (dedup.js) holds the shared state: `pihti-mesh-view`
  (still | 3d, global, default 3D) and `pihti-mesh-up` (a JSON map of
  lower-cased file path → axis; only flips away from the default are stored,
  capped at 500). The default comes from the `data-mesh` URL's extension:
  `.ipt`/`.iam` → Y, anything else → Z. A page without the line (the live
  service's cached old templates) keeps 3D and never reads Still.
- viewer3d.js: `UPS` table per axis (two horizontal axes with a × b = up and
  the home eye). Z is unchanged (mesh_render ISO_EYE). Y is eye (1, 1, 1) in
  Inventor axes: azimuth 45° between Z and X, elevation atan(1/√2). `create`
  takes `up`, `show(mesh, { up, section })`, `setUp(axis)` re-homes,
  `setSection(s)`, `facing(axis)`. Double-click home uses the current axis;
  the key light is in view space so lighting is the same for both axes.
- Section: `{ axis, at, side }`. The plane goes to the shader as `uClip`
  (mesh space, `vMesh` varying); `discard` beyond it. `side` is taken from the
  eye when an axis is chosen, so the half toward the reader is cut away;
  choosing the same axis again keeps the place and asks the eye again. While a
  section is set, back faces shade at 0.55. The derivative normal always faces
  the viewer, so its pre-flip sign carries nothing; the darkening keys off
  `gl_FrontFacing`, which is the same sign the payload's winding-derived
  normals have. Only while a section is set, so a mesh with inverted winding
  does not turn dark in normal viewing. Fragment precision is highp where
  available (mm-scale coordinates in the clip test). Section resets when
  another file is shown and on a lost context; an up flip keeps it.
- Lost context: inspector, part page and dialog each dispose the viewer,
  replace the canvas with a fresh clone (`PihtiMeshTools.freshCanvas`, the
  dialog's old close code) and create a new viewer on the next load: in the
  inspector the next file, a resize, or 3D again; on the part page 3D again.
  Nothing is created eagerly.
- Enlarge: opens with the small view's up axis and a copy of its section;
  its own controls change only the dialog, except an up flip, which is a
  per-file choice: it is remembered and handed back (`onUp`) so the small
  view follows. Its Still | 3D is local to the dialog (a flip inside a modal
  does not change the global default behind it). Opened in Still it shows the
  still filling the stage (`object-fit: contain`); 3D there fetches through
  the page memo (the dialog's one `fetchMesh`; the test now allows exactly
  that one). Enlarge in the inspector is live in Still for any file with a
  mesh URL.
- viewer3d.js is now 517 lines; the test cap moved from 480 to 560.

## Changed paths

- `src/pihti_dedup/static/viewer3d.js`
- `src/pihti_dedup/static/dedup.js`
- `src/pihti_dedup/static/dedup.css`
- `src/pihti_dedup/templates/_file_tile.html`, `catalog.html`, `part.html`
- `tests/test_web.py` (new tools-line markup test; viewer line cap; dialog
  fetch assertion)
- `pyproject.toml`, `src/pihti_dedup/__init__.py` (0.25.0)
- `README.md`, `.agents/CHANGELOG.md`, `.agents/dedup-viewer-design.md`

## Verification

- Gates: pytest, ruff, `node --check` on both scripts, `git diff --check`
  (results in the handoff report).
- Scratch server on 127.0.0.1:4199 (scratch `PIHTI_DEDUP_CACHE_ROOT`,
  `session_factory=lambda: None`, so Inventor was never reached; process tree
  killed, port free; the live 4185 untouched). Browser pane at 1700×1000
  emulation; the pane's screenshots of an emulated viewport are illegible, so
  the canvas was read back (preserveDrawingBuffer patched in for inspection)
  and layout measured by `getBoundingClientRect`.
  - `bellows_flange.ipt` in the inspector opens Y up, matching Inventor's own
    thumbnail orientation (slots and bolt holes in the same places); Z up
    stands it on edge; the flip is stored and cleared on flipping back.
  - Sections on Z (50 % and 30 %), X and Y cut the half toward the eye; the
    exposed inside reads darker.
  - Inspector preview 307 px tall and the tools line at the same top before
    the mesh, with 3D, with a section, in Still, and after a lost context.
  - Still: no `/mesh/` request on hovering another `.ipt`; Enlarge opens the
    still filling the dialog; 3D inside the dialog fetches and draws, global
    view stays Still.
  - `WEBGL_lose_context` on the inspector canvas: still shown, canvas
    replaced; the next file draws in 3D on the new canvas.
  - Part page `bellows_flange.ipt`: canvas takes the still's 512×512 exactly,
    box height unchanged; `bellows.iam` in 3D shows "too large" with the
    toggle on 3D.
  - `CF150-spacer.stl` opens Z up; Enlarge carries Z up and a Z section at
    70 %.
  - No script errors (only the known 404s: favicon and the too-large mesh).

## Next

- Possible follow-up, not in directions.md: solid section caps via the
  stencil buffer (draw back faces incrementing, front faces decrementing,
  then fill the plane where the stencil is odd).
- The owner's eye on the tools line at his widths (1400–2560): the pane
  could not show a legible screenshot of an emulated desktop viewport.

## Usage

- Provider: Anthropic; implementation agent: Claude Opus 5.5 (child of the
  orchestrator); observed 2026-09-25 JST.
