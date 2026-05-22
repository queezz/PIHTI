# Drawings and PDFs

## Where the drawing files live

Fabrication drawings and exported PDFs are stored in `Drawings-PDFs/`.

They are not organised by subsystem — the folder is a flat archive accumulated over
the lifetime of the project. File names generally follow the part or assembly name
from Inventor, sometimes with a date suffix.

## Inventor drawings vs. PDFs

Each fabrication drawing is an Inventor drawing file (`.idw`) linked to one or more
`.ipt` or `.iam` files. The drawing dimensions are associative: if the part geometry
changes, the drawing updates automatically.

PDFs are point-in-time exports of those drawings. They represent the state of the
part *at the time of fabrication*, which may differ from the current Inventor model
if the design was later revised. The PDF is the reference for what was actually
built.

When a part is revised after fabrication, the old PDF should be kept — it documents
what is physically in the lab, not what the model currently says.

## Using drawings for fabrication

Drawings sent to a machinist or vendor should always be PDF exports, not `.idw`
files. Include:

- overall dimensions and tolerances
- material specification
- surface finish requirements where relevant (especially for vacuum parts)
- a cross-section view for any turned or bored part
- thread callouts for tapped holes and threaded features

If a drawing was updated after the first fabrication run, check the revision block
or filename for a version indicator before re-sending.

## Relationship to the Inventor models

Not every part in the repository has a formal drawing. Many parts — especially
brackets, spacers, and enclosure panels — were machined directly from the 3D model
or a quick sketch. The drawing archive is not complete.

For parts that do have drawings, the `.idw` file lives in the same folder as the
part or assembly it documents, or in `Drawings-PDFs/` if it was exported there
during a fabrication run.

## Historical drawings

Some PDFs in `Drawings-PDFs/` are scans or exports of drawings that predate the
Inventor models. These exist as manufactured references only — there is no
corresponding parametric model, and dimensions should not be assumed to be exact.

If you are working on a system that has only historical drawings, model the as-built
geometry from physical measurements where precision matters.
