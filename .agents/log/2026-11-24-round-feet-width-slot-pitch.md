# Round fabricated widths and dimension the slider pitch

## User requests and implementation

Change the guide spacer and all three carriage feet from 56.8 to 57 mm in
the parts and drawings. The base profiles had coordinate-defined corners,
not width parameters. Moved their four corners symmetrically from Y=±28.4
mm to ±28.5 mm. Verified each actual solid width is 57 mm, all downstream
mounting sketch point coordinates are unchanged, and all active features
remain healthy. The 53 × 40 mounting pattern is unchanged.

On sheets 05–07 replace the two centre-to-outer-slot 114 dimensions with
associative 53 mm dimensions between the slots on each slider block. Retain
the 61 mm centre-to-inner-slot offsets and ±20 mm row positions. Update the
Japanese explanation accordingly. Sheet 08 and all three feet display the
actual 57 mm model width, not a rounded override.

## Verification

Recorded initial loaded documents, PIHTI.ipj, parent constraints and occurrence
transforms. All five loaded referring assemblies updated with healthy active
constraints and no component transform changes. Saved four parts and their
five parents deliberately; drawing native health and saved-copy reopening
passed with all 373 annotations attached and views current.

Read-only where-used index confirmed the three carriage modules and two
native drawing referrers. The legacy sliding-assembly-monotaro.idw was not
modified; the requested fabrication publication is Bellows-Monotaro-A4-JIS.

Initial coordinated drawing edit was stopped by automatic review when the
new model-width request arrived. Replaced that plan with the coordinated
part-and-drawing change after inspecting and trialing the native geometry.

## Paths

Four parts: monotaro-front-flat-carriage-plate.ipt,
monotaro-middle-flat-carriage-plate.ipt, monotaro-rear-flat-carriage-plate.ipt,
SBI20FL-flat-spacer-15.ipt under bellows-probe.
Five parent assemblies: monotaro-front-module.iam, monotaro-middle-module.iam,
monotaro-rear-driven-carriage.iam, monotaro-bed-module.iam,
sliding-assembly-monotaro.iam. Main fabrication IDW and workshop PDF updated.

Final checks: rendered sheets 05–08 reviewed; PDF text checks confirm 57 mm widths, direct 53 mm pitch and no old 114 offsets. Both PDFs retain nine links. Refreshed all nine affected STEP mirrors; final baseline returns to 1,075 current, four pre-existing stale and one missing. Two unrelated BoronProbe Doctor findings remain unchanged. Task-owned documents closed before guarded STEP exports; exporter releases its own opens. git diff --check passed.
