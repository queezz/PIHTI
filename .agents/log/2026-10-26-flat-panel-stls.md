# Lay panel STLs flat for printing

## Goal

Owner requested front and rear STL panels lying down instead of standing in
native CAD orientation.

## Changed

- Rotated both panel binary meshes with a proper rigid rotation: print X = CAD X,
  print Y = CAD Z, print Z = 3 mm - CAD Y. Exterior panel faces lie at Z = 0;
  ears point upward. No remeshing, scaling, mirroring or native CAD edits.
- Updated the print manifest with exact transforms, hashes, mesh bounds and bed
  contact areas; updated the print README and rebuilt the complete ZIP.

## Verification

- Front footprint 74 x 60 mm, height 11 mm; back footprint 74 x 60 mm, height
  19 mm. Both minimum Z values are exactly 0. Broad bed contact areas are
  about 3333.95 and 3973.58 mm2 respectively.
- Original triangle counts retained: front 3328, back 5476. Both remain
  watertight, consistently wound and positive-volume. Rigid-transform inverse
  agrees with original coordinates within 0.00001 mm; volume unchanged within
  0.0001 percent. Normals rotated with vertices.
- The other nine STL file hashes are unchanged. All native source hashes still
  match the manifest. ZIP CRC check passed and every entry matches its file.
- notes check retains only the two existing unrelated summary findings;
  git diff --check passed. No CAD or runtime software changed.

## Next

Reload the corrected front/back STLs, or use the updated complete ZIP.
