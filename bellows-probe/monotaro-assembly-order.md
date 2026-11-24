# Monotaro bellows assembly order

1. Fit the table, backing plates and rails. Load the guide blocks with their transfer retainers and leave one lead screw end support open.
2. Thread the single TR16 drive nut onto the lead screw before fitting the second support and its thrust stack. Orient the nut flats to match the saddle.
3. Fit the rear foot and saddle to the guide blocks. Seat the TR16 nut flats in the saddle and install the separate keeper with four M4 × 12 screws. Fit the flange clamp to the driven foot.
4. Seat the vessel-end steel spacer against the 51101 shaft washer, then secure the outer retaining washer with the axial M5 × 10 cap screw. Verify seating, usable thread and bottom clearance. At the wheel end fit the split collar and the tapped ASH125 with its set screw on the shaft flat. Check drive alignment and set thrust endplay.
5. Install the bellows and vacuum hardware in the clamps after the mechanical bed and drive are assembled.

The Inventor bed contains the threaded nut and the rear driven carriage subassembly. The main assembly links their axial travel to the rear vacuum module. The rear vacuum module contains the rear bellows flange and attached vacuum hardware.

## Drawing publication

Sheet 01 indexes fabrication sheets 04–18. The purchased ASH125 is separate:
only its radial M5 tap is made by the shop, following assembly sheet 03.
Sheet 23 is the Japanese supply reference. The workshop PDF is
[`Bellows-Monotaro-A4-JIS.pdf`](Bellows-Monotaro-A4-JIS.pdf). Its blue order
codes link to MonotaRO.

To retain those links on re-export, run the stages in this order:

1. Export all 23 native sheets to a temporary unlinked PDF (`<raw.pdf>`) in scratch.
2. Run `pihti-dedup pdf-strokes <raw.pdf> <temporary-thin.pdf> --pages 1-23 --allow-image-xobjects`.
3. With an external Python environment containing `pypdf`, run
   `python bellows-probe/add-monotaro-pdf-links.py <temporary-thin.pdf> bellows-probe/Bellows-Monotaro-A4-JIS.pdf`.

The helper verifies the codes, links and unchanged page text. The adjacent
`monotaro-pdf-links.json` stores normalized native note bounds: regenerate
those bounds if sheet 23 moves its order codes. Use the temporary Inventor
export as the input to the line-weight pass.
