# Insert the bypass tee ahead of the o-ring gauge port

## Goal

Attach the already placed CF-70-Tee:1 in sliding-assembly.iam at the gauge
port's CF70 connection, rigid and non-rotating, as the owner's bypass port.

## Changes

- Inserted the existing library tee between CF114-CF70-zero-length-adappter:2
  and pipe-o-ring-gauge-port-assembly:1, with its straight bore coaxial to the
  probe pipe. The gauge-port assembly moves outward by 124.968 mm, the tee's
  outer flange separation; its previous rotational orientation is retained.
- Suppressed the previous direct attachment Rigid:60 and added two rigid
  joints: Bypass tee to bellows adapter - rigid, and Gauge port to bypass
  tee - rigid. The tee branch points upward, 30 degrees from vertical in
  the existing flange clocking.
- Saved sliding-assembly.iam, retaining the owner's existing edits there.
  Shared tee and gauge-port source files were not edited. Other live owner
  CAD changes remain outside this commit.

## Verification

- Both new joints have rigid type 102401 and healthy status 11778.
- Mating flange-center gaps measured below 0.000001 mm at both joints.
- All active constraints and joints in sliding-assembly and its open
  PIHT-Bellows-probe parent are healthy after update.
- Inspected the native Inventor bitmap: tee inserted, branch upward, o-ring
  gauge port in front, probe pipe passing through the straight bore.
- git diff --check passed. No software changed; earlier same-session Ruff
  and 525-test gate apply to the unchanged tooling.

## Next

The branch is available for the owner's bypass connection. No bypass hose,
valve, gasket or flange bolts were added by this task.
