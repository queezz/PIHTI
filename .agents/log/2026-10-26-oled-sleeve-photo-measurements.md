# Symmetric sleeve grips from owner photograph

Use correct screw holes as datum and allow for printed part error.

Owner clarified that the bolts thread into the printed screen-mount, the actual
holder is symmetric, and its CAD envelope may differ. Manual picks of four bolt
centres were mapped to the known 23.1 x 23.56 mm screw pattern by a homography.
Three paired side-edge samples give widths 31.81, 31.95 and 31.91 mm. Estimate
about ±0.5 mm uncertainty: blurred/layered edges, parallax and different surface
planes prevent precision metrology. Nominal 32 mm is a trial input, not an
asserted exact physical dimension.

Added key printed_holder_width=32 mm. Set cavity width from this plus 0.3 mm
clearance each side; outer width stays 34.2 mm. Corrected the grips too: native
sketches prove left intervals [-16.35,-15.95] and right [15.95,16.35] mm about
the screw-pattern centre. Thus 0.05 mm nominal grip is symmetric. Original
holes, aperture and holder remain untouched. All 20 features remain healthy,
including the owner's five printability features. Native seated check clears
screen and hardware; only the known mismatched CAD holder contacts. Removed
prior travel results from current verification since they predate these grips.

Changed sleeve, fit fixture, verification JSON, folder README, changelog and
this log. Physical fit still needs a test print; tune printed_holder_width and
fit_interference as needed. Do not mistake nominal photo-derived values or
CAD holder overlap for validation of actual friction fit. Prior symmetry log
records the intermediate CAD-envelope-based correction, superseded here.
