# Upper sleeve grip engagement and top-window enlargement

Engage the short upper mount wall and clear the screen when viewed from above.

## Changes

Owner reported that the upper rib does not retain and requested a 1.5 mm upward
window extension. Added key window_top_extension=1.5 mm; aperture grows from
22.4 x 12 to 22.4 x 13.5 mm. Bottom stays -4.473210808 mm; top increases from
7.526789192 to 9.026789192 mm in display frame. Width and outer shell unchanged.

Upper rib sketch now references its own plane at upper_grip_start=base_height
+ upper_grip_rear_gap=4.3 mm, versus 4.95 previously. Rib moves 0.65 mm toward
panel and spans Z=4.3..6.3 mm. Gap to panel is 0.15 mm. Lower rib, horizontal
and vertical fit spans (both 28.6 mm), side knobs and owner mates unchanged.

Window increase crowded Chamfer4's terminal-pocket lower rim. Rolled back
failed trials; trimmed only the unused lower 0.6 mm of that hidden pocket,
keeping its upper edge and original chamfer treatment. Pocket height 3.4 mm;
modeled terminals still clear. All 21 existing features are healthy. Original
printed mount unchanged by hash. Pre-edit native backup is outside workspace.

## Verification and changed paths

Measured upper rib/mount intersection with transient solid Boolean: 1.5679 mm3
before, 7.1786 mm3 after. This proves increased geometric engagement, not force.
Whole-sleeve Boolean checks are independent of hidden occurrence visibility:
OLED, four M2 screws and front panel all zero overlap. Mount intersection is
71.2381 mm3 including intended fit features. Do not equate hidden-component
AnalyzeInterference zero results in older logs with physical clearance.

Changed sleeve, fit fixture, native views, current checks, READMEs, print STL,
manifest/ZIP, changelog and this log. STL: 5536 triangles, closed, consistent
winding, positive volume, Z minimum zero. Size remains 31.6 x 35.7096 x 15.5416 mm;
bounds error below 0.000001 mm, volume error 0.00439 percent. All other ten STL
hashes unchanged. Current sleeve source hash and ZIP payloads/CRC verified.
Interior native image inspected. Native section state was preserved. No runtime
code changed. All unrelated owner CAD, extra STL, attachments and 3MF untouched.

## Next steps

Test print for actual top retention and viewing angle. Tune upper_grip_rear_gap
if needed; window_top_extension adjusts only the top. No claim of physical
retention before that test.

Targeted diff check and MkDocs strict build passed. Notes check retains only
the two pre-existing missing summaries in BoronProbe_2026 and Plasma Vessel_2026.
