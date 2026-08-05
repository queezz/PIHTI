# Mesh preview spike — STL/STEP/DWG verdicts and integration contract

Date: 2026-08-05
Agent: opus (spike), recorded by fable

Read-only spike; repo untouched at the time. Working code preserved in
`.agents/spikes/mesh-preview/` (`meshpreview.py`, `dwgpreview.py`,
`PROPOSED_geometry_preview.py`, `test_degenerate.py`). This entry is the
contract for the preview-integration chunk queued in `directions.md`.

## Verdicts (tested on every matching repo file)

| Format | Verdict | Success | Timing |
|---|---|---|---|
| STL | in-house, numpy+Pillow z-buffer renderer | 168/168 | median 0.54 s, max 2.79 s |
| STEP | needs dep: `cascadio>=0.1.1` + `trimesh` (abi3 wheel, no compile, ~46 MB installed) | 69/69 | median 1.05 s, max 6.99 s |
| DWG | in-house, embedded-PNG extraction, zero deps | 21/21 | ~0.01 s |
| 3MF | bonus, works via trimesh (+networkx, lxml) | 22/22 | median 0.93 s |
| DXF | NOT covered — known gap (6 scanner-visible files) | — | — |

STL inventory: 167 binary + 1 ASCII; largest 648k triangles. Degenerate
inputs: 16/16 handled (raise `EmptyMeshError` → caller uses placeholder).

## Hard-won gotchas (do not rediscover)

1. Rasterizer windows must be rectangular per-axis, not square `max(w,h)` —
   fixed 31.7 s → 2.1 s worst case. Render cost tracks screen-space triangle
   size, not count (slowest STL had only 1,372 triangles).
2. **cascadio cannot open non-ASCII paths** (OpenCascade IO) — all Japanese-
   named STEP files fail. Stage through an ASCII temp path.
3. DWG preview inversion must key on mean luminance, not the corner pixel
   (paper-space sheets otherwise invert to black).
4. Loosening cascadio tolerance does NOT speed conversion (cost is the STEP
   parser, not tessellation) — keep max quality.

## Integration notes for the builder

- `geometry_preview.render()` should return the existing
  `inventor_meta.Preview` dataclass; never raise (return `None` → existing
  `placeholder_svg` fallback).
- STEP costs seconds → **disk cache required**, keyed
  `sha256(normcase(path), mtime_ns, st_size, size, RENDERER_VERSION)`,
  temp-then-replace writes, sharded under a gitignored store.
  `RENDERER_VERSION` in the key supersedes stale styles.
- Whole-repo cold build ≈ 218 s → add a `warm-previews` CLI subcommand;
  don't let the catalog page trigger 200 renders.
- Extras: `preview = [numpy, pillow]`, `step = [cascadio, trimesh]`; probe
  imports in `available_extensions()`; graceful placeholder when absent.
- Couplings to update: `PreviewCache.get` and `_part_context` gate on
  `INVENTOR_EXTENSIONS`; `templates/_results.html` hard-codes
  `('.iam','.idw','.ipn','.ipt')`. `CAD_EXTENSIONS` already lists the new
  formats.
- The blanket `Cache-Control: no-store` after_request hook should exempt
  `/preview/...` once rendering is real.
- DWG caveat: embedded previews are 180×180 paper-space sheets — cap upscale
  at 2.5×, centre on a card; grid-quality only.
