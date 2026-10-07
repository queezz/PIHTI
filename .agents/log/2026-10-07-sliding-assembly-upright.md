# Correct upright sliding assembly

Corrected the user's reported upside-down placement. Rotated the whole assembly
180 degrees about assembly Y and translated it so clamp-foot:2's actual bottom
face (local Z=15 mm) lies at assembly Z=0. Replaced the earlier origin-plane
flush with a named zero-offset face-to-XY mate. Grounded states retained.
Rail local X axes are parallel to assembly Z and point -Z, putting the bases
below the moving assembly. This supersedes the earlier +Z interpretation.
All 20 constraints are healthy; native update succeeded; foot minimum Z is zero
within 1e-7 cm and both rail X/Z dot products are -1 within 1e-7. Left unsaved
in Inventor for inspection. Unsuccessful attempts were rolled back.
