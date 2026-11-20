# Echelle grating support from reference photos

- Goal: bring the owner's grating-support mockup closer to the photographed
  spectrometer and represent its separate aluminum plates.
- Read the saved prototype and selected November 20 phone photos from the NAS.
  No desktop capture, live browser access, window activation or UI input.
  Native document API only; PIHTI project verified.
- Preserved `Echelle/echelle-grating-mount-mockup.ipt` unchanged. It has no
  referring assemblies. Created `echelle-grating-support.iam` and base, roof
  and side IPTs alongside it: four plates, three part types.
- Approximate envelope 200 × 108.161 × 140 mm. Provisional common stock 10 mm;
  opening 50 × 100 mm. Retained the owner's 26.5° angle. Dimensions, alloy and
  roof end treatment remain mockup assumptions, documented in the folder README.
- The base owns shared user parameters; native derived parameter tables feed
  the roof, side and assembly. All geometry sketches are fully constrained.
  The right side has three healthy flush constraints; the other components
  are grounded at the common origin.
- Native verification: all features/constraints healthy, references resolved,
  one solid per part, four assembly occurrences. Stock 9 mm and restored 10 mm
  both passed interference analysis with zero results; the right side moved
  from x=191 to x=190 mm while the envelope width stayed 200 mm.
- Exported all four new STEP mirror copies. Saved-file Doctor: zero active
  blockers; all Echelle mirror copies current. Pre-existing deferred items
  remain the stale BoronProbe_2026_non-bellows assembly and missing C25K22A4CU
  mirror. The live Doctor initially retained a stale inventory entry, then
  flagged the assembly template's `Standard (mm).iam` fossil. Its existing
  Recheck Inventor endpoint confirmed this is not an actual direct reference
  and recorded the verification. The assembly Doctor now says Nothing to fix.
  No unrelated repairs.
- Verified the assembled/exploded preview rendered from exported geometry.
  STEP preview meshes use meters; convert to mm before adding exploded offsets.
- Task began with no loaded Inventor documents. All task-owned background
  documents closed; none remained after native verification.
- Unrelated owner modification to `3D-printing/jis80-glass-115-retainer.3mf`
  left untouched. No software changes; native checks and whitespace gate apply.
- Next: confirm actual stock thickness, envelope and opening on the hardware
  before using the mockup for fabrication or detailed mounting design.
