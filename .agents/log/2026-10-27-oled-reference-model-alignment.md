# OLED reference model aligned to the proven mount

Treat the owner's matching printed holder and bores as authoritative; correct the OLED.

## Measurements and implementation

Mount Sketch3 gives four 2 mm bores on a 21 x 23 mm pattern. The seating-plane
centre in mount coordinates is (0,0,10.540446486) mm. Downloaded OLED bores used
23.1 x 23.56 mm, with pattern centre 0.35 mm below the PCB centre. Prior photo
calibration used that incorrect downloaded pitch and is historical evidence only.

Edited the existing shared STEPs/OLED-128x64-0.96.ipt in place, without another
CAD copy in the workspace. Four native MoveFace features shift the hole groups:
X inward 1.05 mm each, upper row Y+0.07 mm, lower row Y+0.63 mm. Two more native
features translate upper copper-pad bodies to follow their bores. PCB outline
26.7 x 27.86 mm, display, header and eight imported bodies remain intact. The
pre-edit native copy is in machine-local scratch outside the repository.

Placed the grounded OLED PCB underside centrally on the unchanged mount seat.
World translation from prior pose: (0.065778483,0.023941410,-1.05) mm. Moved four
M2 screw origins onto the corrected hole axes, seating at PCB top; original
orientations/visibility retained. The source plastic mount was not edited.

Cover window and header pocket shift -0.403210808 mm in its display plane.
Concealed screw pockets now follow the corrected module's 21 x 23 mm pattern.
Outer dimensions, 22.4 x 12 mm window size, 0.6 mm chamfer, horizontal and vertical
28.6 mm fit spans, owner finishing and three cover mates remain unchanged.

## Changed paths and verification

Shared imported OLED part; modular-sensor-box sleeve/fixture/checks/README and
native review images; print STL/README/manifest/ZIP; changelog and this log.

Native PCB bores verified 21 x 23 mm. All four axes meet mount holes at the seat
within 1.89e-14 mm. PCB centre is exactly X=Y=0 in the mount frame. Actual active
screen face centre agrees with aperture within 3.11e-14 mm. OLED has 14 healthy
features and eight bodies; cover has 21 healthy features; owner mates healthy.
Cover has no assembly interference. Tiny screw/PCB-copper contacts remain,
0.0138–0.0286 mm3; distinguish these from the resolved cover overlaps. Mount
file hash before/after unchanged in this task. Native front images inspected
with and without the cover. Loaded referencing-assembly scan found only the fit
fixture; original logger placement was not opened or rewritten. The shared
source correction applies when its other referring assemblies are loaded.

Refreshed high-resolution face-down millimetre STL: 5564 triangles, watertight,
consistent winding, positive volume, bounds error below 0.000001 mm, volume
error 0.00414 percent. Original ten STL hashes preserved. Current sleeve source
hash, ZIP CRC and every archive payload checked. Original mount export still
records the prior source version; owner's unrelated mount-source edits remain
unstaged. No runtime tooling changed. Physical snug-fit retest remains pending.

## Next steps

Use the physical-fit-tested mount, rather than the original downloaded hole
pattern, for future OLED variants. Tune grip parameters after the next print.
Leave unrelated owner CAD, pictures, extra STL and 3MF untouched.

Targeted git diff --check and MkDocs strict build passed. Notes check has only
the two pre-existing missing summaries in BoronProbe_2026 and Plasma Vessel_2026.
