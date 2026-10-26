# Symmetric OLED sleeve fit and larger knobs

Preserve owner fit changes, centre the grips and take up horizontal and vertical play.

## Decisions

Owner changed printed_holder_width to 30 mm and cavity_width to that width,
removing the 0.6 mm allowance, and removed the pad lead-ins and Chamfer3. Their
side grip span was 29.6 mm with a 0.15 mm lateral bias. First centred it while
preserving its size, then followed the owner's steering to enlarge both side
knobs by another 0.5 mm per side (1 mm total). Key side_grip_span is now 28.6 mm.
Pad profiles mirror at X=[-15.05,-14.3] and [14.3,15.05] mm in bolt-centred frame.

A shell-height reduction did not regenerate; all trials were rolled back.
Added two internal stops instead, each 1 mm inward, 22 mm wide and 2 mm high at
the existing pad station. Vertical stop faces at Y=±14.3 mm leave 28.6 mm between
them versus the original 30.6 mm cavity. Key vertical_fit_reduction=2 mm controls
total take-up. The finished exterior, opening, screw pockets and current owner
finishing remain. Owner's pre-edit native copy saved outside the workspace.

## Paths and verification

Changed sleeve, fit fixture, checks, current part images including new interior
view, folder README, STL/manifest/README/ZIP, changelog and this log.
All 21 current features healthy. Native dimensions verify both grip symmetries.
The owner's three healthy mates now control the review cover. Fixture contacts
include the source holder and three M2 screws (0.3143, 0.3143, 0.7204 mm3), so this
fixture does not prove physical clearance. Temporary alignment trial restored;
owner mates and locations preserved. Do not repeat the intermediate no-contact
result from before the current fixture update. Original holder source is also
owner-modified since its older export; it was left unstaged and its STL unchanged.

STL: 5564 triangles, watertight, consistent winding, positive volume. Face down
at Z=0, 31.6 x 35.7096 x 15.5416 mm. Bounds error below 0.000001 mm, volume error
0.00414 percent. Current sleeve source hash verified. All ten other STL hashes
unchanged. ZIP CRC and all payloads verified. Source-native export now uses the
display sketch transform rather than the old cap occurrence the owner removed.
No runtime tooling changed. Physical retest remains required.

## Next steps

Print revised cover and tune side_grip_span / vertical_fit_reduction from actual
fit. Photo estimate is superseded by owner's print feedback. Leave unrelated
CAD, attachments and 3MF untouched.

MkDocs strict build passed. Notes check retains only the two pre-existing missing
summaries in BoronProbe_2026 and Plasma Vessel_2026. Targeted diff check passed.
Owner-created sensor-box-oled-sleeve-trial.stl is left untouched; refreshed
canonical bundle file is sensor-box-oled-sleeve.stl.
