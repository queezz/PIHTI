# Bellows table holes and drawing sections

Rebuild the plate with Inventor Hole features and review section placement across the A4 drawing set.

- Changed `bellows-probe/monotaro-bellows-plate.ipt` and `bellows-probe/Bellows-Monotaro-A4-JIS.idw`. The four native Hole features define 36 M6 × 1 taps, 12 extrusion holes with countersinks, 8 backing holes with countersinks, and 4 Ø6.6 support holes. Retired cut features are suppressed.
- Measured all 20 seat cones at Ø11.2 at the top and Ø5.5 at 2.85 mm depth. Inventor regenerated the sliding assembly and found zero plate interferences with all 20 modeled flat-head screws. Their modeled top faces sit flush. Verify the purchased screws against the selected cone before machining.
- Reattached the table dimensions to the new hole geometry, locked 12 section sketches in their parent view coordinates, and visually reviewed the A4 proofs. The keeper leader and section markers clear the holes. The thrust spacer section cuts through the bore and reports 3 mm.
- The drawing remains at machining review. This pass checks plate/fastener fit and drawing presentation. It does not rerun the full 700 mm motion study or establish whether the existing middle-foot relief can be removed.
