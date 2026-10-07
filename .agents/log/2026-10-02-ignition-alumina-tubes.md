# Ignition alumina clamp tubes

## Goal and decisions
Added the two requested alumina tubes around the M3 ignition-help support in
pihti-for-simulation-flat.iam. Bore is 3.2 mm for M3 clearance. OD is provisionally
6 mm because the user does not yet know the measured diameter. The lower tube
runs from ring-pre-anode's top Z to ignition-help's bottom Z; the upper runs
from ignition-help's top Z to preanode-screen's bottom Z. Their ends sandwich
the ignition wire's axial thickness. Both occurrences are grounded as requested
for placed parts. Original source parts were not modified.

## Changed paths
Plasma Vessel/ignition-alumina-tube-lower.ipt (24.187373 mm long)
Plasma Vessel/ignition-alumina-tube-upper.ipt (8.826943 mm long)
Native tubes have separate Alumina material and ivory Ceramic appearance assets.
Description records provisional dimensions and unverified physical properties.
Added occurrences Ignition-alumina-lower:1 and Ignition-alumina-upper:1 to the
active assembly, left unsaved for review. No STEP exported yet.

## Verification
Native part updates succeeded. Both are grounded. Z endpoints match the clamp
limits within 1e-7 cm. Volumes match analytical annular-cylinder volumes within
1e-6 cubic cm. Each part contains an editable annular sketch and extrusion.

## Next steps
Inspect and save the assembly, then let the STEP mirror export the saved file.
Confirm measured OD and actual alumina grade before simulation material setup.
