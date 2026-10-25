# Simplify spacers and restore instrument access

## Goal and owner steering

Simplify the new spacer parts to plain blocks and straight holes. Queezz will
add chamfers and fillets. Bring in the existing OLED unchanged; provide rear
USB and SD-removal openings. Shorten the front panel ears by fixing them closer
to the panel in the intentional front wire gap.

## Changes

- Both spacer parts now have exactly three features: one plain 7 x 13 mm
  rectangular extrusion, a 3.6 mm rod bore and a straight 4.6 mm insert bore.
  Removed the stepped wing extrusions, collar recesses, unused collar parameter
  and orphan workplanes. No spacer chamfers or fillets were introduced.
- Reoriented front spacer occurrences outward and moved their screw/insert
  axes from y = 32 to 45 mm. Back axes stay at -32 mm. Same two spacer parts
  are reused at both ends; the middle of the 5 mm wire gap remains clear.
- Shortened front returns from 21 to 8 mm. Rear returns remain 16 mm.
  Return inner faces were extended inward 0.3 mm to meet the uniform 7 mm
  spacer faces; outer screw seating faces are unchanged, thickness is 3.3 mm.
- Referenced the original OLED, screen mount and four M2 screws in their
  original positions. Queezz explicitly requires the existing snug fit.
  Restored the original 30 mm opening, 2 mm corner radii and 0.5 mm entry
  chamfers exactly; shared OLED and mount geometry were never modified.
  Do not enlarge the opening to clear nominal interference: this fit worked
  physically and is intentional (owner, 2026-10-26).
- Rear rectangular openings: USB 14 x 7 mm centred at assembly x = 0.72,
  z = 20.16 mm; SD access 20 x 10 mm centred at x = -11.25, z = -5.5 mm.
  Openings stay square-edged for owner finishing.
- Updated the native fixture, fit-check.json, README and native PNG previews;
  added rear-access.png and plain-spacer.png.
- At entry the owner had saved changes to the fit assembly and removed the
  rear panel return-root fillet. Preserved that removal and the current
  placements; related saved panel/assembly work is included in this revision.
  Existing unrelated CAD changes remain outside the commit.

## Verification

- Native fixture has 56 occurrences. Reopened saved references resolve;
  all features of all four new parts are healthy (11778), one solid each.
- No new part-to-part collisions. Against retained electronics/display/frame,
  the only reported contacts are eight intentional insert/pilot fits and
  the restored OLED seat. Its nominal mount contact is 44.6286868377 mm3,
  matching the original assembly to less than 0.000001 mm3.
- Unchanged sleeve clears the revised assembly at y = 2.8 mm centre.
- Front removal with OLED/mount/M2 screws traveling with the panel, and rear
  removal: clear at 0, 2, 10 and 30 mm with panel screws removed.
- Modeled SD card: clear through rear opening at 0, 5, 10 and 20 mm withdrawal;
  at 20 mm the card is fully outside the rear panel. Verified proxy pose in
  root coordinates before testing. No temporary card occurrence was saved.
- Original logger folder: all 320 native file hashes remain unchanged.
- Native front, rear and plain-spacer previews visually inspected.
- git diff --check passed. notes check has the same two pre-existing missing
  summary findings in BoronProbe_2026 and Plasma Vessel_2026; no finding in the
  edited folder. No software or published MkDocs source changed, so the prior
  525-test/Ruff/strict-build result was not rerun for these native CAD edits.

## Next

Queezz will add finishing features. Physical insert fit, chosen USB plug and
finger access still need a hardware trial. Button details and humidity/ADC
specific connections remain future layout work.

## Fit correction before commit

An initial enlargement of the OLED opening was rejected by the owner because
his existing snug fit works. Automatic approval review blocked the pending
commit for that conflict. Restored the proven seat before retrying; the final
geometry and verification above supersede that abandoned clearance change.
