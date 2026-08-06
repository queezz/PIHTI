# STL, STEP, 3MF, and DWG previews — pihti-dedup 0.6.0

**Date:** 2026-08-06
**Agent:** opus
**Goal:** productionize the 2026-08-05 mesh-preview spike. About 250 CAD files
in this workspace carry no embedded thumbnail, so the catalog, the part page,
and the duplicate rows showed them all as the same grey placeholder — exactly
the files a visual triage needs most, since an `.stl` or `.step` export has no
iProperties to read either.

The binding contract was `log/2026-08-05-mesh-preview-spike.md`; this entry
records what changed against it.

## Decisions

- **Three modules, one front door.** `mesh_render.py` (rasterizer),
  `dwg_preview.py` (container reader), and `geometry_preview.py` (dispatch,
  cache, availability). Only the front door is imported by `web.py` and `cli.py`,
  and it has **no optional import at module scope** — numpy, Pillow, trimesh,
  and cascadio are probed with `find_spec` and imported inside `render()`. An
  install without the extras degrades to placeholders instead of failing to
  import, and `available_extensions()` is the single truth about what this
  install can draw.

- **`render()` never raises.** Every failure path — corrupt geometry, a missing
  file, an absent extra, a WMF-only DWG — returns None, and the existing
  `placeholder_svg` fallback catches it. That is what lets the route keep its
  current shape: a preview that cannot be produced is not an error condition,
  it is the state most of the workspace was in yesterday.

- **The disk cache is positive-only.** `.pihti-dedup/previews/`, sharded two hex
  characters deep, temp-then-replace writes, keyed
  `sha256(normcased path, mtime_ns, st_size, render size, RENDERER_VERSION)`.
  Storing misses was rejected: a negative entry would outlive its reason —
  installing the `step` extra does not invalidate a "STEP cannot be rendered"
  marker — and `web.PreviewCache` already memoizes misses for the life of the
  process, which is what the repeated-request case actually needs.

- **The cache lives inside the workspace, unlike the quarantine.** The
  quarantine was moved to `../PIHTI-quarantine/` by hand because
  `UsingUniqueFilenames=Yes` lets Inventor's filename search reach into
  `.pihti-dedup/` and bind to a quarantined CAD file. A preview is a `.png`,
  which is not a CAD extension Inventor resolves, so the same hazard does not
  apply. `.gitignore:25` (`.pihti-dedup/`) covers it —
  `git check-ignore -v .pihti-dedup/previews/ab/x.png` confirms — and
  `inventory.DEFAULT_SKIP_DIRS` already skips the directory during scans.

- **`/preview/...` is the one route exempt from `no-store`.** Every other page
  reports live filesystem state a cached copy would misreport. A preview is
  keyed by the file's own modification time, so a validator is exact rather than
  optimistic: the response carries `Last-Modified` and an ETag over path, mtime,
  size, `RENDERER_VERSION`, and whether this is a real preview or the
  placeholder — installing the `step` extra turns the latter into the former
  without touching the file, and the validator has to notice. Marked
  `private, no-cache`, so the browser always revalidates and gets a 304 rather
  than being trusted to time out.

- **`warm-previews` is a command, not a page trigger.** A cold whole-workspace
  build costs minutes, almost all of it the STEP parser. Loosening cascadio's
  tolerances does not help — the spike established that the cost is parsing, not
  tessellation — so quality stays at maximum and the work moves off the request
  path entirely.

- **`_results.html` no longer hard-codes the Inventor extensions.** The
  `('.iam','.idw','.ipn','.ipt')` tuple gating the Rename link is now
  `RENAMEABLE_EXTENSIONS`, exported as a Jinja global. It was already a
  duplicate of `renames.RENAMEABLE_EXTENSIONS`; adding four previewable
  extensions to the same page was exactly the moment it would have drifted.
  A test now pins that an `.stl` member row shows a preview but no Rename link.

## Deviations from the spike contract

- **The `step` extra also carries `networkx` and `lxml`.** The spike's
  integration note said `step = [cascadio, trimesh]`, but its own verdicts table
  had already flagged 3MF as needing them. trimesh defers its 3MF loader and
  raises `ModuleNotFoundError` from *inside* the loader rather than at import,
  so with the two-package extra every 3MF render failed at runtime. They are in
  the extra now, and `available_extensions()` probes for them so a partial
  install skips 3MF instead of logging 22 warnings.

- **DWG needs only Pillow, not numpy.** `available_extensions()` gates `.dwg` on
  Pillow alone and the mesh formats on numpy as well, so a Pillow-only install
  still gets its drawings.

## Changed

- `src/pihti_dedup/mesh_render.py` — new, from the spike's `meshpreview.py`.
  `load_stl` (binary and ASCII, size arithmetic deciding which), `load_trimesh`,
  `load_step`, `render_triangles`, and the bucketed rasterizer.
- `src/pihti_dedup/dwg_preview.py` — new, from the spike's `dwgpreview.py`.
  `extract_preview` deliberately imports nothing optional so the container
  format is testable without Pillow.
- `src/pihti_dedup/geometry_preview.py` — new. Extension sets,
  `available_extensions`, `missing_extra`, `preview_source`, `cache_key`,
  `cache_path`, `render`, `get_or_render`, `warm_previews`.
- `src/pihti_dedup/web.py` — `PreviewCache` takes the workspace and dispatches
  Inventor vs geometry; `preview_image` gains validators; the `no_store` hook
  exempts the preview endpoint; `_part_context` reports `preview_source`;
  `RENAMEABLE_EXTENSIONS` exported as a Jinja global.
- `src/pihti_dedup/cli.py` — `warm-previews [workspace] [--include-vendor]
  [--quiet] [--json PATH]`, with per-file progress and a counts line.
- `templates/_results.html`, `part.html`, `catalog.html`, `static/dedup.css` —
  the shared extension set, a preview-source caption, and the corrected rail
  note.
- `pyproject.toml` — `preview` and `step` extras; version 0.5.0 → 0.6.0, matched
  in `src/pihti_dedup/__init__.py`.
- `AGENTS.md`, `README.md` — install command now `".[dev,preview,step]"`, plus a
  short Previews section in the README.
- `.agents/CHANGELOG.md`, `.agents/directions.md`, `.agents/dedup-viewer-design.md`.
- **Deleted `.agents/spikes/mesh-preview/`.** The four spike files are
  superseded by the production modules and their tests; the verdicts, timings,
  and gotchas remain recorded in `log/2026-08-05-mesh-preview-spike.md`, and the
  code itself remains in Git history at `9abcb97`.

## State

- `pytest -q` — **164 passed** (was 113 at 0.5.0; +51). New: 18 in
  `test_mesh_render.py` (the spike's 16 degenerate cases ported to synthetic
  fixtures, plus ASCII-staging and a missing STEP), 9 in `test_dwg_preview.py`
  (synthetic DWG containers, BMP header synthesis, luminance-keyed inversion,
  upscale cap), 15 in `test_geometry_preview.py` (key sensitivity, sharding,
  disk cache hit/miss, unwritable cache, missing extra, warm counts), 2 CLI, 7
  web/route. No CAD binary from the workspace is committed as a fixture.
- `ruff check src tests scripts/find_duplicates.py` — clean.
- `git diff --check` — clean.
- Flask test client only; no live server was started.
- Spot-checked against real workspace files: `.stl` 1.50 s, `.stp` 1.39 s,
  `.step` 1.64 s, `.dwg` 0.02 s, `.3mf` 1.16 s — all producing PNG.
  `staging/hayashi/SpectroscopySystem/Downloads/コリメータ.stp` renders in
  1.06 s through the ASCII staging path, which is the gotcha's live proof; the
  tracked tree has no non-ASCII STEP, but ten sit in `staging/` and the
  `BoronProbe_2026/parts/ICF70TE/ボディ*.ipt` set shows the naming is normal
  here.
- No CAD file was read for anything but its preview, and none was written.

## Next

- DXF is the remaining gap and is now recorded in `directions.md`: six files, no
  embedded raster to unpack, so it needs a real 2D renderer rather than an
  extraction.
- `RENDERER_VERSION` is 1. Any change to `mesh_render.Style`, the camera, or the
  DWG normalization must bump it, or stale PNGs will be served.
