# Bolt the upward CF70–NW40 adapter and copy its KF clamp

## Goal

Owner requested flange bolts on ICF70_to_KF40:2 and the matching KF clamp,
using the existing gauge-port clamp as the mounting example.

## Changes

- Added six workspace M6x35-HexCS.ipt bolts and six M6-nut.ipt nuts through
  the tee branch and adapter CF70 flange. Bolt heads seat on the tee side;
  nuts seat on the adapter rear face. Each has a rigid joint.
- Added ContentCenter/NW/NW40_clamp.ipt at the adapter's KF40 end, with
  a rigid joint to that adapter.
- Reproduced the working example's concentric placement: clamp origin at
  adapter-local (0,-40.767,0) mm, clamp Z axis along adapter +Y. An existing
  centered circular clamp edge provides the joint origin; its -6.095 mm
  joint gap accounts for the offset between that edge and the KF flange
  reference face, not a physical flange separation.
- Saved only sliding-assembly.iam; shared component sources unchanged.

## Verification

- Six branch holes used once each; 12 fasteners and one clamp added with
  13 rigid joints.
- Bolt and nut axes verified along the tee branch axis.
- Clamp lateral offset below 0.00001 mm; axial center and axis direction
  match the existing gauge-port example within numerical tolerance.
- All active relationships in sliding-assembly and PIHT-Bellows-probe healthy
  after update. Inspected native bitmap of bolts and seated clamp.
- git diff --check passed. No software changes; same-session Ruff and
  525-test pass cover unchanged tooling.

## Scope

Other owner CAD and metadata edits remain outside the commit. No new mating
KF fitting, centering ring, seal or bypass hose was introduced.
