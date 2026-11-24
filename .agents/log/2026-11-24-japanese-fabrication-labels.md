# Japanese fabrication labels and larger plate view

## Goal and decisions

Make fabrication sheets easy for the Japanese machine shop to read, with an
unmissable quantity. Translate sheets 04–18 titles, material notes, machining
notes, leader callouts and English dimension suffixes. Retain linked dimension
values, reference-only material status, and the unconfirmed h7 proposal.

Use a consistent bold 5 mm quantity at the upper right: 製作数量 for fabricated
parts and 加工数量 for the purchased nut and screw receiving additional work.
Use appropriate counters (個, 枚, 本). Show allocation below totals for the six
spacers and four upper/lower clamp halves. Native sheet names also become
Japanese, updating their associative compact footer titles.

Enlarge sheet 04 plate view from 0.4 to 0.5 (1:2), a 25% linear increase.
Recenter the view and separate bottom dimensions into three rows. Keep the
upper dimension tiers below the header. Move sheet 10 section label below
its view to avoid the new quantity field. No model geometry changes.

## Verification and changed paths

Native IDW and both PDF variants regenerated; the workshop PDF is curated.
All 373 dimensions/centerlines/center marks remain attached, views current,
loaded model references and active feature/relationship health pass. Saved
copy reopens cleanly. Review all fifteen fabrication sheets in rendered PDF.
Both published PDFs retain nine MonotaRO links and omit the previously removed
supplier-browsing instructions.

Inventory refreshed: 1,392 CAD files. Doctor/STEP baseline remains unchanged:
1,080 models, 1,075 current mirrors, four stale, one missing; two unrelated
BoronProbe missing-reference findings (ICF70F 1個付き 19穴.ipt and ICF70-34-hole.ipt).
The stale bellows assembly mirrors predate these drawing-only edits.

Changed curated paths: bellows-probe/Bellows-Monotaro-A4-JIS.idw,
bellows-probe/Bellows-Monotaro-A4-JIS-man.pdf, and this log.

Final rendered sheet 04 and sheet 10 checked with no annotation overlaps. PDF checks passed for all fifteen Japanese quantity fields and nine links in each variant. Task-owned invisible drawing closed; no loaded documents remain. git diff --check passed.
