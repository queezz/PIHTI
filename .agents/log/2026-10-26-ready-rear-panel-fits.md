# Reuse the ready rear panel's proven fits

## Goal

Owner requested all ready rear panel geometry, including the printed USB/SD
openings, other openings, chamfers and fillets. Do not substitute estimated
rectangles or alter working fits.

## Changes

- Replaced the new rectangular USB/SD cuts with exact native solid tooling
  taken from ElectronicsBox/esp32-ambient-logger/temp-logger-back-plate-v2.ipt.
- Transferred all four openings: USB, SD, DC power and thermocouple. Original
  shaped entries, internal radii and chamfers are preserved analytically.
  No corresponding power/thermocouple hardware was added.
- Matched the ready panel's inner 0.5 mm perimeter chamfer too. The full flat
  74 x 60 x 3 mm panel body now matches the donor; the new removable ears,
  their bores, owner fillets and 3 mm root chamfers remain intact.
- Four consumed Exact ready opening native solid features drive one Boolean
  cut in the new part. This is an exact geometry snapshot, not a live link or
  a guessed re-sketch; original source CAD remains unchanged.
- Updated fit-check.json, README, overview/detail/rear PNGs and the fit assembly.

## Verification

- Native comparison of the complete flat panel region: donor material volume
  11950.000875394273 mm3; new volume 11950.000875394278 mm3; common volume
  11950.000875394273 mm3. Symmetric difference about 0.000000000004 mm3,
  below the 0.000001 mm3 comparison threshold.
- Separate aperture-region comparison also matches. All material outside
  that region stayed identical before the explicit perimeter match; that
  later change only touched the flat plate, not the inward mounting ears.
- All 142 untouched referenced/source file hashes checked unchanged during
  the transfer. New part remains one solid; every feature is healthy 11778.
  Saved fixture reopens with all references resolved.
- SD card withdrawal through the original opening is clear at 0/5/10/20 mm.
  Front panel with OLED is clear through 0/2/10/30 mm withdrawal. Sleeve clear
  at its existing y = 2.8 mm seating centre.
- Found pre-existing owner ear-root gusset contacts against the two sandwich
  plates, about 23.759 mm3 per plate. Their bounds lie entirely inward of
  the flat panel, y >= -45 mm in assembly coordinates, outside all transferred
  material. They remain at seated/small withdrawal positions and clear by
  10 mm. Preserved and reported; no claim of a fully interference-free seated
  rear assembly. Do not alter the printed opening fits to fix these roots.
- Native rear preview visually checked. notes check has only its two existing
  unrelated missing-summary findings; git diff --check passed.
- Native CAD/docs only. No rerun of unchanged software or published-doc gates.
  Failed import trials were aborted before any save; explicit solid output
  and separate opening cutters completed the exact transfer successfully.

## Next

Review the new ear-root finishing against the sandwich plates before printing.
The ready-panel face and opening fits are now proven geometry and stay fixed.
