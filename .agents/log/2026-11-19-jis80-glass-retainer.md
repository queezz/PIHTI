# Adapt the yellow PLD retainer to the ICF152 adapter

## Goal and decisions

Kuzmin requested a retainer for the opposite face of his ICF152 adapter,
using the yellow FDM vessel retainer as the basis. His photos show four
holes and an O-ring face, consistent with JIS VF/VG80 rather than ISO-F100.
He confirmed the existing FDM vessel gasket fits the groove as supplied.
Use the nominal JIS80 Ø160 / Ø135 PCD / four Ø12 pattern, keeping the
existing Ø115 × 10 glass and retainer recess. Photos are not precision
metrology; do not describe the bolt pattern as a measured adapter survey.

## Changed

- New independent `PLD/jis80-glass-115-retainer.ipt`, plus STEP and mm STL.
- New `PLD/jis80-glass-115-window.iam`, retaining the original glass and
  healthy rigid joint, replacing only the retainer in an assembly copy.
- `PLD/jis80-glass-115-window.md` records dimensions and the supplier source.
- No original PLD files or unrelated bellows changes were edited.
- Follow-up: Kuzmin requested the printable STL under `3D-printing/`.
  Moved it there after checking the PLD and shared-library native files for
  references to the STL filename (none found), verified SHA-256 unchanged,
  and updated the file notes. Native models and STEP remain in `PLD/`.

## Verification

- Native retainer: one solid, all six features healthy (11778).
- Reopened assembly clean, both references resolved, rigid joint healthy.
- Glass occupies the original 10 mm recess with the original seating.
- Independent STEP inspection found Ø160 outside, Ø115.4 recess, Ø100
  opening and four Ø12 cylinders at radius 67.5.
- STL bounds: 160 × 160 × 13 mm. Rendered and inspected both faces.
- Minimum nominal radial ligaments: 3.8 mm to recess, 6.5 mm to outside,
  before inherited chamfers. Glass radial clearance is 0.2 mm.
- Original retainer and assembly SHA-256 unchanged by the copy operations.
- PIHTI.ipj verified. Inventor initially had zero documents open. All
  task-owned documents were released; zero remained after final checks.
- No software changes, so no software test suite run.

## Next

Fit-check the printed ring on the physical adapter with the existing glass
and gasket. Adapter, gasket, bolts and washers are outside the two-part
window assembly's scope.
