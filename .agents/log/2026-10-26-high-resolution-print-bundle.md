# Export the finished box for printing

## Goal

Owner finished the fillets/chamfers and requested high-resolution STLs.
Complete the paused named ear-thickness work and export the final geometry.

## Changes

- Both panels now have real key user parameter ear_thickness = 4 mm. Each of
  four profile widths and the screw-clearance depth is linked to it; the right
  clearance plane is 30 mm + ear_thickness. Inner spacer-contact faces remain
  fixed. Moved only the eight panel screw seating poses outward to x = +/-34 mm.
- The old tab_thickness parameter only drove clearance-cut depth. It is renamed
  and genuinely linked to geometry. Grounded inner profile edges hold ear
  reach and position while the thickness grows outward.
- Owner finished the rear fillets during the pause. Final parameter work did
  not delete, recreate, rename or change any finishing feature. The prior
  rebind trials were aborted; the final 4 mm update is healthy with his finishes.
- Rear before/after flat-panel solid comparison is identical (0 mm3 difference),
  so the owner's final openings and fitted faces were not changed.
- Archived owner's final panels and shared base-plate finishing with the fixture;
  unrelated original logger assembly and bellows work remain unstaged.
- Created 3D-printing/modular-sensor-box/: eleven binary high-resolution STLs,
  export-manifest.json, README with per-box quantities and a ZIP bundle.
- Enclosure has three named solids: case, retainer, grip. Exported each separately
  via an unsaved temporary native part; no duplicate native parts were created.
  Remaining exports are both panels, both spacers, base plate, shelf, short
  spacer and OLED mount. Quantity list covers a complete box; double for two.
- Updated design README, fit-check.json and native overview/detail/rear previews.

## Verification

- Read-only pre-export duplicate inventory: 1,221 CAD files; 19 repeated-name
  groups, 12 differing-byte clashes, 7 exact-copy name groups, 14 other-name
  exact-copy groups. No CAD cleanup/import performed.
- Every exported source was saved, current and feature-healthy. Source SHA-256
  hashes still matched after export and are embedded in the manifest.
- Native STL translator: Resolution=0 (High), ExportUnits=5 (millimetres),
  OutputFileType=0 (binary), one file per exported part/solid, colour disabled
  and internal mesh-node movement disabled. Option values checked against
  Autodesk's official translator reference linked in the manifest and README.
- All eleven files pass binary triangle-count/length, finite coordinates,
  watertightness, consistent winding and positive-volume checks in trimesh.
  Compared against native PreciseRangeBox and solid volume. Maximum volume
  difference below 0.08%; maximum bounding-coordinate difference below 0.000004 mm.
  Ordinary RangeBox was too conservative for the OLED mount, so the actual
  precise native bounds were used instead of weakening the scale check.
- ZIP validates with no CRC errors and contains eleven STLs, README and manifest.
- Final assembled check: only the preserved nominal snug OLED contact remains.
  Earlier ear-root contacts are resolved by the owner's final finishing/frame
  work. Sleeve clears at y = 2.8 mm centre. Front and rear travel at 0/2/10/30 mm
  and SD withdrawal at 0/5/10/20 mm are clear.
- notes check retains only its two pre-existing unrelated summary findings;
  git diff --check passed. Native CAD/fabrication only; no repeat of unchanged
  software gates or published-doc build was needed.

## Next

Use the ZIP or individual STL files. Files retain CAD coordinates: orient and
place them on the bed in the slicer. Test the 2.5 mm direct-M3 plastic pilot.
The grounded fit fixture's screw poses need adjusting if ear_thickness is
changed later; individual part profiles and clearances update from the parameter.
