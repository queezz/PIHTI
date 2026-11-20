# Lengthen the clamp hand opening to 75 mm

## Goal and change

Kuzmin requested 75 mm overall hand-opening length in his clamp master.
The authoritative part is `bellows-probe/flange-camp-114.ipt`; the assembly's
two halves are derived parts, so their trees do not contain the source sketches.

- Changed Sketch6 parameter d50 from 60 to 75 mm, keeping the opening
  centered. d51 remains 15 mm; existing fillets and other dimensions remain.
- Updated and saved the master and both derived parts with healthy features
  and no missing references. Lower-half geometry is unchanged.
- Refreshed the upper STL in `3D-printing/bellows-stage-fit-test/`, its
  manifest/source hashes and README. Kept the unchanged lower STL.

## Verification and session safety

- PIHTI.ipj verified. The master and both derived parts were already loaded
  and clean. No documents were opened or closed; owner documents remain open.
- A broader proposed save of loaded parent assemblies was rejected by
  automatic approval review before execution. The successful operation was
  limited to the authorized master and two derived parts. Parent assemblies
  and the owner's existing dirty drawing were not saved by this task.
- Verified the hand-opening sketch's horizontal span is 75 mm and its
  height remains 15 mm. All edited-part feature health statuses are 11778.
- Master volume: 297.448878 → 292.832993 cm³. Upper: 130.343624 →
  125.727739 cm³. Lower stays 167.105254 cm³.
- Fine upper STL: 571,692 triangles; 196.1747 × 87.5 × 20 mm bounds;
  every welded edge has two incident triangles, no collapsed triangles.
  Rendered and inspected the longer opening. Export uses 0.005 mm absolute
  linear deflection and 1 degree angular deflection from the updated solid.
- Doctor/STEP preflight and post-save checks reported zero active reference
  blockers. Refreshed all three edited parts' STEP mirrors through Inventor
  and recorded successful exports against the actual saved source stamps.
  All 12 print-bundle manifest entries match their source and STL hashes.
  No software changes, so software tests were not rerun.

## Next

Reload the upper STL before printing. When the dimensioned drawing is next
updated, review the hand-opening dimension and layout against the new model.
