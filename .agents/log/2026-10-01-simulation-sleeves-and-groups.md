# Simulation sleeves and suppression folders — 2026-10-01

## Goal and decisions

Owner saved a reduced flat assembly and requested fresh STEP inspection,
replacement of stacked ceramic rings, and unit suppression of the boron target
and window meshes. Owner will discuss holes and simulation requirements with
Claude directly; no message was sent to another chat.

The mirror already auto-exported the owner's save. Explicit refreshes were
exported atomically from the saved open assembly and recorded through StepMirror.
No mirror software defect was established and no tooling changed.

## Changed

- Plasma Vessel/pihti-for-simulation-flat.iam
- Plasma Vessel/pihti-simulation-ceramic-sleeve-10x6x110.ipt
- This handoff.

The starting owner-edited assembly contained 88 occurrences and three assembly
cuts. Replaced 33 contiguous rings (11 per feed) with three sleeves, 10 mm OD,
6 mm bore, 110 mm length, placed on their measured original axes. Extrusion 1
also cuts the new sleeves. Shared source rings were not modified. Sleeve was
created as a simulation-specific copy of the native ring extrusion.

Browser folders retain the flat structure and existing feature participants:
insulators (3 sleeves), Boron target (11 remaining occurrences 138–149),
Window meshes (adapter 123, large cylinder 175, port cylinder 180).
Window parts remain suppressed; boron remains unsuppressed.

## Verification

Read-only duplicate inventory: 1187 CAD files, 19 repeated-name groups and
12 conflicting hash groups. Correct PIHTI.ipj active. Saved and reopened
assembly has 58 top-level parts and three healthy assembly cuts. Actual folder
Suppress command suppressed all 11 boron parts; an informational BOM dialog
blocked completion. Owner dismissed it and closed without saving. Reopening
restored the saved unsuppressed boron state, folders and sleeves.

Fresh STEP readback: 85 to 55 active occurrences, all BRep shapes valid.
Cut ceramic volume: 5222.231768950463 to 5222.231768950485 mm3.
All 52 other active occurrence volumes unchanged within 1e-5 mm3.
Rendered the actual STEP through OCC tessellation and visually inspected it.
Final mirror entry is current and the assembly is saved clean.
Prior same-session tooling gates passed (504 tests, Ruff); no tool changes.

## Next and limits

Tungsten grouping is pending exact component identification. Owner says wires
do not touch and sit inside a SUS retainer. Preserve physical separation;
joining into one connected solid would require additional geometry. The existing
filament IPT has two native solids: hidden Solid1 and visible Solid3; STEP
exports only its visible solid. HighCurrentFeedRod occurrences 30, 34 and 38
carry Copper metadata; do not infer that these are the owner's tungsten wires.

Inherited material metadata is not simulation-ready: the ceramic source and
new sleeve say Polystyrene, the filament says Generic. These are existing
labels, not verified physical materials; simulation material assignments need
review. No holes were filled and no shared hardware part was edited.
