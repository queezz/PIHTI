# Fabrication Notes

Overview of available shop processes and what kinds of parts each is suited for.
This is a working reference, not a manual.

---

## Wire EDM (wire cutter)

Cuts conductive material (steel, copper, aluminium, brass) by electrical discharge
along a programmed wire path. Produces very accurate 2D profiles with no cutting
force on the workpiece.

Good for:

- flat flanges and plates with precise bolt circles
- thin-walled parts that would deflect under milling forces
- internal cutouts that cannot be reached by a mill
- stainless steel and hardened materials that are difficult to machine conventionally

Export: DXF from Inventor drawing or part sketch. Confirm tolerances and material
in the drawing notes before sending.

---

## Milling machine

General-purpose metal removal. Used for facing, pocketing, slotting, boring, and
drilling on a coordinate table.

Good for:

- aluminium enclosure panels and structural brackets
- flanges that require face machining or stepped features
- parts that need multiple setups and tight tolerances across faces
- prototype vacuum parts before committing to EDM or turning

Most of the aluminium profile brackets and enclosure panels in `ElectronicsBox/`
were milled. Plasma-facing parts with complex port geometries were typically turned
and milled in combination.

---

## Drill press

Column-mounted drilling for holes that do not require precise positioning.
Used for through-holes in plates, clearance holes, and initial hole placement before
reaming or tapping on the mill.

---

## Lathe

Turning for rotationally symmetric parts: nipples, adapters, spacers, shafts,
flanges with a circular cross-section.

Most vacuum nipples, feedthroughs, and port adapters in `Plasma Vessel/`, `PLD/`,
and `PALP/` are turned parts. Export a 2D drawing with diameter, length, and
surface finish callouts. Cross-sectional view is essential.

---

## Laser cutting

2D cutting of sheet material (metal, acrylic, thin aluminium). Faster than EDM for
sheet parts that do not require tight tolerances.

Output files live in `LaserCutting/`. DXF is the standard exchange format.
Check kerf compensation if the part is designed for press-fit assembly — the laser
removes material and the resulting part is slightly undersized relative to the
nominal DXF.

---

## 3D printing (FDM)

Used for enclosure parts, brackets, cable guides, jigs, and non-structural mockups.
Not suitable for vacuum-side parts or anything exposed to heat or plasma.

Output files live in `3D-printing/`. STL and 3MF are both present. Check orientation
notes in the print file before slicing — some parts have preferred orientations for
layer adhesion and support access.

The `PLD/` folder contains test geometry (`test-triangle-overhang.ipt`,
`test-internal-cone-overhang.ipt`) used to characterise overhang limits before
printing functional parts.

---

## General notes

- Always confirm material availability before finalising dimensions around stock sizes.
- For vacuum parts, surface finish and cleanliness matter more than tight tolerances
  in most cases. Call out finish requirements explicitly in the drawing.
- When a part is modified after fabrication (reworked, re-drilled, etc.), note it in
  the assembly README or drawing so the Inventor model and physical part stay in sync.
