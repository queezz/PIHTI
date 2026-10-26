# OLED sleeve symmetry correction

Correct the unequal side borders while preserving owner printability finishing.

## Evidence and changes

Owner reported asymmetry after adding Chamfer3, Fillet5, Chamfer5, Chamfer4
and Fillet6. Owner photo confirms the actual mount is symmetric and the existing
holes are correct; CAD holder geometry may differ. Treat the existing M2 screw
pattern as the lateral datum, not the offset CAD holder envelope.

The screw pattern/OLED centre is at holder X=-1.05 mm. Previously the sleeve
was centred at holder X=0. Shifted inner and outer footprints to X=-1.05 and
widened them by 2.1 mm to preserve modeled holder clearance. Final outside
34.2 x 32.1 mm; equal 5.9 mm side borders around the unchanged 22.4 mm aperture.
Added key holder_oled_offset and sleeve_center_x controls. Left pads reach
the unchanged holder contact positions; right pads stay in place. Hardware
pockets, aperture, original holder and all module locations stay unchanged.

Modified sleeve part, fit fixture, verification JSON, three review images,
folder README, archive changelog and this log. The owner-finished pre-edit
native copy was saved outside the workspace in machine-local scratch.

## Verification

All 20 final native features healthy, including all five owner finishing features.
Only holder pad contacts seated (0.5462113 mm3 after owner's finishing). Outward
travel at 0, 0.2, 0.5, 1, 2, 5, 10, 15 and 20 mm has no other contacts.
Final seated transform restored and saved. Front and oblique native images
refreshed; front image inspected for equal borders. A zero-pad sensitivity test
failed regeneration after owner finishing; restored 0.05 mm interference and
all features healthy. Do not reuse pre-finishing parameter-sweep results as
evidence for the finished sleeve. Finished print manifest sources and meshes
still match their hashes. No runtime tooling changed.

## Next steps

Physical sleeve fit test remains pending. Keep the correct holes as reference
if the modeled holder differs from the printed hardware. Unrelated owner work
and the new owner 3MF are outside this change.

MkDocs strict build and git diff --check passed. Notes check has only the two
pre-existing missing summaries in BoronProbe_2026 and Plasma Vessel_2026.
