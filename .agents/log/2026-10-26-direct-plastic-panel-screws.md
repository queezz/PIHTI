# Use direct plastic threads for panel screws

## Goal and owner decision

Queezz finished the spacer and panel edges and chose M3 screws directly into
printed plastic, without heat-set inserts. A worn spacer is a quick replacement
print rather than a reason to retain inserts (owner, 2026-10-26).

## Changes

- Upper/lower spacer transverse pilots changed from 4.6 to 2.5 mm as an initial
  print-test value. Renamed the driving parameter to panel_screw_pilot and the
  cut to Straight M3 plastic screw pilot. Existing owner fillets/chamfers
  survived and remain healthy. Rod bores, lengths and installed poses unchanged.
- Removed only the eight Panel insert occurrences from SensorBox-panel-fit.iam.
  Kept the eight existing shared M3x8 button screws.
- Preserved the owner's already-saved panel finishing; neither panel geometry
  was edited. Their finished native files are included with the owner-finished
  spacers so the archived fixture and feature evidence describe the same state.
- Updated README, fit-check.json and the four existing native previews.
  Original/shared CAD and unrelated owner changes were not saved or staged.

## Verification

- Saved fixture reopened with 48 occurrences, all references resolved and no
  brass-insert reference. All four local part feature trees remain healthy.
- Mounts clear all retained components when excluding their own panel screws.
  Eight nominal screw/pilot contacts are intentional thread-forming engagement.
- All 141 other referenced files, including both owner-finished panels and the
  OLED/mount, retained their input hashes during the operation.
- Native preview inspected. notes check reports only the same two unrelated
  missing-summary findings in BoronProbe_2026 and Plasma Vessel_2026.
  git diff --check passed. No software or published docs source changed;
  no repeat of unchanged software gates was needed.
- Fit-check retains previous panel/SD withdrawal and sleeve evidence; their
  geometry and paths were not changed by this pilot/hardware change.

## Next

Test the nominal 2.5 mm pilot with the actual print and M3 screw; tune the named
parameter if needed. Hardware thread life is not proven by the CAD overlap.
