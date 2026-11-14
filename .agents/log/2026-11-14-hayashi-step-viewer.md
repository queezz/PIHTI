# Open the Hayashi optics setup in the STEP viewer

- Goal: unblock work on `Hayashi-probe/hayashi-setup-with-optics.iam`, whose
  current mirror was rejected at the fine display tessellation.
- Keep the triangle budget and retry at coarser display tolerances. Count
  mesh triangles before expanding their coordinates, clear cached fine
  tessellation on retries, and invalidate cached viewer refusals.
- Changed the STEP mesh builder, display cache version, regression tests,
  tool version and changelog. No native CAD, mirror or part map was changed.
- Tested the actual mirror: 521 occurrences and 1,135,443 display triangles,
  under the existing two-million-triangle limit. The regression checks budget
  enforcement and that a coarser display preserves both fixture occurrences.
- Next: use the STEP viewer for picking and annotations; use the native
  Inventor assembly for geometry edits. Export still uses the original STEP
  geometry.
