# Repair flange attachment during flexible motion

## Goal

Repair the owner's reported separation of a flange from its carriage clamp while
dragging sliding-assembly, preserving the flexible telescoping mechanism.

## Changes and decisions

- Used the running Inventor automation API in the background, under PIHTI.ipj.
- In bellows-probe/bellows-clamped-on-bearings.iam, suppressed Rigid:3 and
  Rigid:4, retaining the original joint definitions for reference. Replaced each
  flange-to-clamp connection with three named constraints: a zero-offset flush
  seat, a concentric cylinder-axis mate, and an origin-plane angle retaining its
  original clocking (150 and 30 degrees respectively).
- The clamp bore is radius 57.25 mm and the flange cylinder radius 57 mm;
  explicit cylinder-axis inference is required. The clamp planar face has its
  parameter orientation reversed, so the correct seat relation is Flush.
- Preserved every original grounded state, the remaining joints, the seven
  previously moved bolts, Flexible, and all existing travel limits. Native part
  geometry and the separate PIHT-Bellows-probe assembly were not edited.
- Saved the repaired subassembly and bellows-probe/sliding-assembly.iam.

## Verification

- Replacement changed the displayed component matrices by at most 2.5e-11.
  All active constraints and joints report healthy and native updates succeed.
- A temporary parent constraint drove clamp-foot:1 through 1, 10, 5 and 0 mm
  travel. Its clamp, flange, tube, bearings and bolts followed together; the
  opposite end stayed fixed. Position error was below 4.9e-10 cm and orientation
  error below 4.4e-14 for fixed attachments. Rolled back the temporary driver and
  restored the starting pose before saving.
- A negative travel test exceeded an existing sleeve extension limit and was
  rolled back. Existing limits include Mate:5 (-485 to -135 mm) and Mate:8,
  Mate:9 and Mate:10 (-200 to 0 mm). No limit was enlarged or disabled.
- The earlier bolt-session motion test used the wrong sign for the temporary
  axial driver; its failure did not establish a defect in the original model.
  The corrected offset equals the carriage's assembly Y coordinate.
- Direct references resolve; both saved documents report clean. No interactive
  mouse drag was performed, honoring the owner's background-automation preference.
- Python source is unchanged from the preceding 522-test passing gate and Ruff
  run in this chat. Whitespace checked for the new evidence. No published docs
  changed and no tool version bump is earned.

## Next

The owner can verify mouse dragging in Inventor. If it still separates despite
the successful native constrained-motion test, capture which component is dragged
and whether Free Move is active before changing any other relationships.
