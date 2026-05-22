# Fabrication Notes

This is an experimental physics lab, not a machine shop. Fabrication is a supporting
capability — the goal is working hardware, not manufacturing perfection. A large
fraction of development happens through printed prototypes, opportunistic use of
available stock, and iteration.

When in doubt about a process or workflow, consult your supervisor before committing
to a design.

---

## Wire EDM (wire cutter)

Use for conductive materials when accurate 2D geometry matters.

Good for:

- complicated internal cutouts
- thin stainless parts
- vacuum flanges and precise plate geometry
- shapes difficult or impractical to mill conventionally

A clear drawing is usually enough. Ask workshop staff what format they prefer — DXF
from Inventor sketches or drawing views is typically sufficient.

---

## Milling machine

General-purpose machining for holes, slots, faces, and custom parts.

Important: aluminium extrusions, profile brackets, and many standard mechanical
elements are bought rather than machined from scratch. Use milling when custom
geometry is actually needed, not as a default.

Workshop CNC capability exists, but discuss it with workshop staff before designing
around it. Not everything is feasible as-drawn.

---

## 3D printing (FDM)

Widely used for prototyping, fixtures, brackets, cable routing, and rapid iteration.
A large portion of experimental development starts with printed parts.

Useful for:

- testing geometry before committing to machining
- checking assembly clearances
- temporary experimental parts and adapters
- ergonomic improvements and cable management
- lightweight holders and jigs

Design for printing when practical: think about print orientation, avoid unnecessary
support structures, and consider layer direction for load-bearing features.

Output files live in `3D-printing/` (STL, 3MF). The `PLD/` folder also contains
dedicated overhang and cone test prints used to characterise printer capability
before committing to functional geometry.

Not suitable for vacuum-side parts or plasma-facing surfaces.

---

## Laser cutting

In-house laser cutting is mainly used for acrylic, plywood, and MDF — panel parts,
enclosure faces, and fixtures.

For simple flat parts: export a face or sketch as DXF. Use an older AutoCAD DXF
format if compatibility issues appear.

Metal cutting is generally outsourced when needed. For precision conductive flat
parts, wire EDM is often preferred.

Output files live in `LaserCutting/`.

---

## Lathe

Used for rotationally symmetric parts: nipples, adapters, spacers, shafts, and
flanges. Most vacuum nipples, feedthroughs, and port adapters in `Plasma Vessel/`,
`PLD/`, and `PALP/` are turned parts.

Provide a 2D drawing with diameter, length, tolerances, and a cross-section view.
Surface finish callouts matter more for vacuum parts than tight dimensional
tolerances in most cases.

---

## TIG welding

Basic TIG capability exists in the lab, including stainless steel work.

Useful for:

- simple frames and support structures
- vacuum hardware modifications
- brackets, stands, and prototype welded assemblies

Good preparation is critical: tight fit-up, accessible weld paths, proper fixturing,
and clean material surfaces. Even non-vacuum welds benefit from careful joint
preparation.

Vacuum-tight welds are achievable but require test pieces and conservative design.
Consult your supervisor before designing welded vacuum components.

---

## General notes

- Confirm material and stock availability before finalising dimensions.
- For vacuum parts, cleanliness and surface finish typically matter more than
  tight tolerances. Call out requirements explicitly in the drawing.
- When a part is reworked after fabrication (re-drilled, modified, etc.), note
  it in the assembly README or drawing so the model and physical hardware stay
  in sync.
- When in doubt about any process or capability, ask workshop staff or your
  supervisor before designing around an assumption.
