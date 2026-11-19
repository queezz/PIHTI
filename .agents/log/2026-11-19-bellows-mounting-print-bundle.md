# Bundle the small bellows mounting parts for print fit tests

- Goal: export the other mounting plates, feet, spacers and screw-retaining
  parts as a self-contained print/reference bundle for Kuzmin and 工作室.
- Added `3D-printing/bellows-stage-fit-test/` with 12 distinct STL parts,
  a linked README with sheet numbers and quantities, and a JSON manifest
  recording source/export hashes, dimensions and checks.
- The full-stage quantities total 25 pieces. A reference set is one of
  each (12 pieces); a complete single carriage needs two guide spacers.
- Reused the current split clamp exports unchanged, relocating them from
  `3D-printing/` into the bundle after a native filename-reference check
  returned no uses. SHA-256 verified before removal of the old locations.
- All source STEP mirror index entries match the current native sizes and
  mtimes. Index keys are casefolded; use the entry's preserved-case path.
- New exports use 0.005 mm absolute linear and 1 degree angular deflection.
  All 12 bounds match source STEP within 0.015 mm; closed-edge tests pass
  after 0.00001 mm coordinate welding. Rendered and inspected all 12.
- Longest included dimension is 246 mm (carriage feet). Long table, rails,
  profiles, lead screw and purchased hardware were excluded.
- Existing clamp meshes had already been checked and remain byte-identical.
  New parts required no collapsed-triangle removal. Total STL size ~46 MB.
- An owner-context COM availability probe returned Operation unavailable;
  no Inventor documents were opened. Current saved STEP copies sufficed.
- Preserved the unrelated bellows IDW, manual PDF, assembly PNG and the
  user's new PLD retainer 3MF. No CAD geometry edits or software changes.
