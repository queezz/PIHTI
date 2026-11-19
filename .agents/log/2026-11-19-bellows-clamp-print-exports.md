# Export the current bellows clamp halves for fit testing

- Goal: Kuzmin requested printable bellows-probe clamps for a physical
  test fit.
- Selected the current `flange-clamp-114-upper.ipt` and
  `flange-clamp-114-lower.ipt`, identified by the November 17 hardware
  handoff as the two parts in `flange-clamp-114.iam`. Older `flangeclamp_up`
  and `flangeclamp_down` are not the selected design.
- Checked STEP mirror index source sizes and timestamps against both native
  parts. Their saved STEP exports also postdate the derived-parts master.
- Tessellated the current solid STEPs with Open Cascade at 0.005 mm absolute
  linear deflection and 1 degree angular deflection, in millimetres.
- Added `3D-printing/flange-clamp-114-upper.stl`: 571,692 triangles,
  28,584,684 bytes.
- Added `3D-printing/flange-clamp-114-lower.stl`: 65,200 triangles,
  3,260,084 bytes. Removed two triangles with coincident vertices emitted
  by tessellation; kept all remaining coordinates and facets unchanged.
- Both meshes have bounds approximately 196.175 × 87.5 × 20 mm, matching
  the individual source STEP bounds within 0.015 mm. Both passed the
  closed-edge check: every undirected edge has exactly two incident facets
  after coordinate welding at 0.00001 mm. No collapsed triangles remain.
- Rendered and visually inspected both halves. Broad faces lie in XY for
  flat printing; import in millimetres at 100 percent scale.
- No native CAD edits or Inventor access. Existing bellows drawing changes
  and unrelated files were preserved. No software tests needed; export
  geometry checks and `git diff --check` are the applicable verification.
- Next: print one upper and one lower for a single clamp test fit. Cosmetic
  CAD threads are not converted into printable helical threads by STL export.
