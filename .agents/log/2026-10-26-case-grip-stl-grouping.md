# Keep grips in the multibody case STL

## Goal

Owner clarified that grips belong to the case's multibody print and receive
fuzzy skin in the slicer, not a separate grip print.

## Changed

- modular-box-case.stl now contains both original case and grip body meshes,
  in their exact original positions. No Boolean union, welding or remeshing
  was applied to the saved triangle data. Retainer stays separate.
- Removed modular-box-grip.stl from the folder and ZIP to avoid an extra print.
  Updated quantities, documentation, source-body metadata and case hash.
- Rebuilt the complete bundle with ten STL files, README and manifest.

## Verification

- Case triangles 161348 plus grip triangles 4064 are retained byte-for-byte
  as 165412 triangles in the combined binary STL. Normals and coordinates
  are unchanged. Both source body meshes are closed and consistently wound.
- Combined bounds match the union of native body bounds; positive volume and
  original body placement checked. The two touching closed meshes are retained
  rather than Boolean-unioned. Coordinate welding during a generic mesh load
  creates non-manifold shared edges; recorded explicitly, not misreported as
  a single watertight welded shell. This reflects the desired multibody layout.
- Remaining eight STL hashes and all native source hashes are unchanged.
- ZIP CRC checks pass; all twelve entries match their current files and the
  separate grip file is absent. Updated print instructions describe the
  intended grip fuzzy-skin workflow.
- notes check retains only its two pre-existing unrelated summary findings;
  git diff --check passed. No native CAD, runtime source or published docs changed.

## Next

Reload the updated case STL or ZIP, keeping the original grip fuzzy-skin
assignment workflow. Retainer remains its own print.
