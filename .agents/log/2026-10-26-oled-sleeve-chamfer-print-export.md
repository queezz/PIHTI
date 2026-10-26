# OLED sleeve chamfer and print export

Replace Soft continuous front edge with a chamfer and export face down.

## Changes

Owner added Chamfer6 since the last checkpoint. Preserved it and the five
previous owner finishing features. Deleted the 0.6 mm fillet while retaining
all dependents, inserted a native ChamferFeature in the same history position,
and kept the requested feature name. Renamed the key driver from top_edge_radius
to front_edge_chamfer (0.6 mm). All 21 native features are healthy.

Exported sensor-box-oled-sleeve.stl into 3D-printing/modular-sensor-box using
Inventor High resolution, binary STL and explicit millimetres. Rigidly transformed
a temporary BRep so the display face points down and rests at Z=0, hollow side
and grips upward. Source native orientation is unchanged. Recorded the transform
and current source hash in export-manifest.json. Rebuilt the complete ZIP with
11 STLs, README and manifest; owner 3MF was not included or touched.

Changed sleeve part, fit assembly, native review images, sleeve verification,
fit-check, folder READMEs, print manifest, STL, ZIP, archive changelog and this log.

## Verification

STL: 5326 triangles, closed/watertight, consistent winding, positive volume.
Dimensions 34.2000 x 35.7096 x 15.5416 mm; minimum Z effectively zero.
Flat front contact area 760.45 mm2. Bounds differ from transformed native solid
by less than 0.000001 mm. Relative volume error 0.00251 percent. All ten previous
STL hashes remain unchanged. ZIP CRC and every archived byte stream checked.
Native chamfer screenshot inspected. No software runtime changed.

## Next steps

Print the sleeve and check the estimated holder friction fit. Symmetry and
photo-derived 32 mm holder assumption remain as documented in the preceding log.
Unrelated owner CAD, attachments and 3MF remain outside the staged change.

MkDocs strict and git diff --check passed. Notes check reports only the two
pre-existing missing summary sentences in BoronProbe_2026 and Plasma Vessel_2026.
