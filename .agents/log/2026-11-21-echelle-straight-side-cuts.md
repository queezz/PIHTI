# Remove the side toes and extend the roof to meet them

- Owner requested removing the sharp triangular foot-like ends, then extending
  the window plate about 5 mm until its lower inside edge meets the side cut.
- Rebuilt the shared side outline with six vertices and a straight lower cut.
  Each removed triangular prism is 249.290804 mm³, matching the calculated
  triangle volume. Both side occurrences update from the one part.
- Extended only the lower roof end by 4.985816 mm along the plate, calculated
  from common stock and angle. The roof's inside lower corner now coincides
  with the side cut at y=27.185996 mm, z=0. The outer corner remains square
  through the stock and projects to z=-4.461978 mm. Upper roof end and opening
  retained. Envelope height is now 144.461978 mm.
- Native checks: healthy features/constraints, fully constrained sketches,
  resolved references and zero interferences. Front plate unchanged; side
  file hash unchanged during the subsequent roof extension. Source prototype
  untouched. Updated assembly and STEP geometry previews, including a saved
  STEP section showing the exact meeting edges.
- Refreshed side, roof and assembly STEP mirror files and recorded export
  provenance. Final scan: every Echelle mirror current, no active Doctor
  blockers. The pre-existing deferred BoronProbe stale/missing copies remain.
- Inventor document ownership was checked at each operation. A guarded batch
  export skipped while the owner had the assembly open; no owner document was
  closed to bypass that guard. The scoped geometry pass preserves pre-existing
  documents and closes only task-owned invisible ones. Final extension pass
  began and ended with no loaded documents.
- Updated README and handoff; whitespace gate applies. No software changes.
  Unrelated owner 3MF modification remains untouched.
