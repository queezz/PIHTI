# Inventor automation how-tos

Verified with running Inventor 2027.1 during October 8–22, 2026. These recipes
supplement AGENTS.md. Old occurrence names, face indices and dimensions must
be checked against current geometry, not copied blindly into an edited model.

## Working preference and starting checks

Queezz prefers background COM work over mouse/keyboard automation. Use the
existing external `~/.venvs/pihti-dedup` Python environment and its `comtypes`.
Read the available Computer Use skill before Windows automation, as required
by that skill. Do not create a repository venv for CAD work.

For a how-to, handoff, or commit of existing files, work from the saved files
and session evidence. Treat any live Inventor command as owner activity unless
the current operation launched it. An `Archon:Render` command can be an active
owner render. Stopping it while diagnosing an export interrupted the owner's
render and Inventor session. Save the native drawing before starting a PDF
export so a translator delay leaves the native changes on disk.

Record Git status, affected documents' dirty states, initial relationship
health, occurrence transforms, grounding and flexibility. Verify PIHTI.ipj
before opening CAD. Select documents by full path: the owner changes tabs
while we work, and display names can collide.

```python
from pathlib import Path
import comtypes.client

app = comtypes.client.GetActiveObject("Inventor.Application", dynamic=True)
workspace = Path.cwd().resolve()  # run from the repository
assert Path(app.DesignProjectManager.ActiveDesignProject.FullFileName).resolve() == (
    workspace / "PIHTI.ipj"
).resolve()
target = (workspace / "bellows-probe/sliding-assembly.iam").resolve()
doc = next(d for d in app.Documents if Path(d.FullFileName).resolve() == target)
```

Sandboxed access to the owner's running COM object failed on this host when
the same scoped owner-context command succeeded. Use a justified tool
escalation when needed; do not infer that Inventor is down from the first
failure. A later owner-context operation-unavailable failure coincided with
no running Inventor process. Distinguish those observations; never kill or
restart Inventor speculatively. Documents may also disappear if the owner
closes them during work; recheck the intended target.

`Documents.Open(path, False)` opens invisibly, **not read-only**. Opening an
already loaded invisible document with `Open(path, True)` made it visible
when `Activate()` alone failed. For guarded rename repair, reuse
[inventor_session.py](../src/pihti_dedup/inventor_session.py) and its existing
workflow instead of building an alternate reference-rewrite path.

## Units, COM collections and proxies

Native length values and coordinates are centimeters: 15 mm is 1.5 and
100 mm is 10. Angle values use radians. Prefer expressions like `"100 mm"`.
Use parameter `.Value` for arithmetic rather than parsing locale-formatted
expressions, which can contain decimal commas.

Collections expose `.Count`, not Python `len()`. Native occurrence collections
supported `ItemByName`; nested `SubOccurrences` did not here, so iterate and
match there. `hasattr()` can propagate comtypes `NameError`; catch access
failures explicitly when investigating optional COM members.

This by-reference output recipe worked for occurrences and nested proxies:

```python
import ctypes
from comtypes.automation import VARIANT, VT_BYREF, VT_DISPATCH, IDispatch

def geometry_proxy(occurrence, native_geometry):
    raw = ctypes.c_void_p()
    output = VARIANT()
    output.vt = VT_BYREF | VT_DISPATCH
    output._.c_void_p = ctypes.addressof(raw)
    occurrence.CreateGeometryProxy(native_geometry, output)
    return comtypes.client.dynamic.Dispatch(
        ctypes.cast(raw, ctypes.POINTER(IDispatch))
    )
```

`geometry._comobj.GetTypeInfo(0).GetDocumentation(-1)[0]` exposed runtime types
such as Plane, Cylinder, Circle and Arc3d. Inspect every SurfaceBody: the CF70
tee has four. Inspect plane normals/root points, cylinder axes/radii and
circle centers. Actual face orientation also depends on `IsParamReversed`.
Revalidate face/edge indices after edits or replacement with another revision.

## Coordinate frames and moving a constrained carriage

A nested occurrence proxy's Transformation was in its containing parent
context. Flexible instances can differ from the source document and from
other parent instances. Compare bearing orientation relative to its carriage;
different carriage travel positions can be legitimate.

```python
# Native point -> assembly context
point.TransformBy(occurrence.Transformation)

# Assembly-context point -> native part frame
inverse = occurrence.Transformation
inverse.Invert()
point.TransformBy(inverse)

# Component B expressed in component A's frame
relative = component_b.Transformation
inverse = component_a.Transformation
inverse.Invert()
relative.PreMultiplyBy(inverse)
```

Cache matrices before looping over cells. Dynamic indexed assignment
`matrix.Cell[2, 4] = value` did not reliably change translation here. Use
`SetTranslation(vector, False)` to retain rotation, then assign the matrix.

For a constrained carriage, ground its driving nut **before** assigning the
transform. Moving first and grounding afterward let the solver discard the
requested position. This verified trial moved the carriage 10 mm:

```python
transaction = app.TransactionManager.StartTransaction(doc, "Trial carriage motion")
try:
    driver.Grounded = True
    matrix = driver.Transformation
    matrix.SetTranslation(app.TransientGeometry.CreateVector(
        matrix.Cell(1, 4), matrix.Cell(2, 4) + 1.0, matrix.Cell(3, 4)
    ), False)  # this model's travel axis; native cm
    driver.Transformation = matrix
    assert doc.Update2(False)
    # Measure actual carriage displacement and relative fastener poses here.
finally:
    transaction.Abort()
```

Measure again after abort/update. Trial solves sometimes changed free travel
poses in flexible parents. Restore recorded positions through the driver,
then restore its original grounding. Never leave temporary grounding in place.

## Workspace fasteners and independent copies

Check `occurrence.Definition.Document.FullFileName`, not the browser label.
The missing-on-another-PC M10 bolts pointed to a machine-local Content Center
cache. Their replacements point under ContentCenter/Fastners.

- Compare geometry and relationship use before replacement. Matching internal
  identifiers and volume supported the copied M10 replacement; they are not
  universal proof of interchangeability between arbitrary parts.
- `occurrence.Replace(path, False)` preserved each installed M10 joint and
  exact transform. Inventor automatically renamed the occurrences, so old-name
  lookup failed. Keep the object or reacquire by its new name. Preserve names
  explicitly when later steps depend on them, after checking uniqueness.
- Delete loose duplicates only after verifying they have no relationships and
  that installed replacements work. Verify count, poses, joints and saved paths.
- Track the actual source with Git. Dropbox folder placement does not prove
  transfer completion to another computer.

`source.SaveAs(new_path, True)` makes a separate copy. Refuse an existing
destination. Copy both the assembly and every dependent part whose geometry
will change; an assembly copy alone still shares its parts. Reuse unchanged
flanges. Set distinct part numbers and verify preserved originals by hashes
or unchanged Git state when preservation is requested.

Measure requested physical faces rather than assuming a length parameter
means overall length. The 65 mm nipple has 65 mm outer-face spacing but a
62.6632 mm copied tube; the original nipple remains 114 mm.

Evidence: [M10 replacement](log/2026-10-22-workspace-m10-bolts.md),
[independent nipple](log/2026-10-22-cf70-nipple-65mm.md).

## Rigid joints and reliable origins

The following worked with geometry proxied into the edited assembly and
intent points supplied in their parts' **native** coordinates:

```python
definition = assembly.ComponentDefinition
origin_one = definition.CreateGeometryIntent(face_one_proxy, native_point_one)
origin_two = definition.CreateGeometryIntent(face_two_proxy, native_point_two)
joint_definition = definition.Joints.CreateAssemblyJointDefinition(
    102401, origin_one, origin_two  # measured kRigidJointType
)
joint_definition.FlipOriginDirection = True  # inspect/test for this geometry
joint = definition.Joints.Add(joint_definition)
assert assembly.Update2(False)
```

Flip flags are geometry-specific. Trial directions and assert the intended
shaft or seal axis with a dot product. FlipAlignmentDirection reversed clocking
by 180 degrees in the tee work. Check flange holes and handle space rather
than forcing an arbitrary branch angle. `joint_definition.Gap` accepted a
numeric cm value; its sign depends on the chosen origin orientation.

A supplied intent point does not guarantee the inferred joint origin. An
arbitrary clamp planar face produced lateral displacement; a centered circular
edge gave a concentric origin. Inspect resulting joint origins and component
transforms, not just healthy status. An origin gap need not be a physical
flange gap: the verified KF clamp uses -6.095 mm to reproduce its example's
adapter-local center (0,-40.767,0) mm. These are part-specific measurements.

Assigning a modified definition through `joint.Definition = ...` failed in
one clocking edit. Transactionally copying with `.Copy()`, deleting the old
joint and adding the modified copy worked. Preserve names/counts, validate
and abort on failure; do not assume all joint types support every change.

## Flexible assemblies, hierarchy and travel

Native promote/demote preserved joint geometry references during regrouping;
browser dragging could silently refuse. The reusable bearing unit was built
from one bearing and its existing bolts. Ground the bearing inside the master;
keep master instances ungrounded and rigid while the carriage stays flexible.
Do not rigid-group the sliding mechanism to hide a local bearing-roll problem.

Temporary single-bearing containers and native demotion preserved external
references while replacing bare bearings with bolted units. This needs a
scoped trial and pose checks, not a blind generic script. See the
[restructuring evidence](log/2026-10-08-reusable-bolted-linear-bearings.md).

Two bearings were upright in the source but rolled 180 degrees in the higher
flexible assembly. Side-plane constraints located them without locking roll.
Flushing the bearing unit's YZ origin plane to the carriage XY origin plane
at -35 mm in that geometry locked orientation while retaining travel. Rebuild
could not fix a degree of freedom still allowed by the constraints. See
[bearing orientation](log/2026-10-08-central-bearing-orientation.md).

Enable MinimumEnabled/MaximumEnabled before accessing new limits' parameter
expressions: disabled new limits returned None. Flange limits alone do not
prove surrogate geometry can reach them. Five 100 mm visual sections per
bellows were needed for 135–485 mm flange spacing. Test both compressed, both
extended and both mixed cases. Abortable trials disabled flange limits and
commanded mate offsets to measure exact endpoints; restore enabled limits
and poses afterward. See [bellows envelope](log/2026-10-22-bellows-travel-envelope.md).

## Fit examples, not universal fabrication specifications

| Connection | Verified recipe | Evidence |
| --- | --- | --- |
| CF70 tee to tapped adapter | Six local M6x25 hex bolts | [Tee hardware](log/2026-10-22-bypass-tee-fasteners.md) |
| CF70 through-hole adapter pair | Six M6x35 bolts plus nuts; two 12.7 mm flanges | [Branch hardware/clamp](log/2026-10-22-bypass-branch-bolts-kf-clamp.md) |
| Front pipe weld flange | Existing PALP/Prototype-PALP-CF70-34-hole-flange.ipt; pipe end at inner land, seal outward | [Weld flange](log/2026-10-22-mizuno-pipe-cf70-weld-flange.md) |

Measure current stacks and distinguish tapped from clearance holes. The weld
flange's 34 mm bore and pipe's 34 mm OD are a zero-clearance nominal CAD fit;
shop tolerance and weld preparation were not specified. The bellows surrogate
tubes are visual/kinematic stand-ins, not telescoping hardware to fabricate.

## Save, validate and hand off

Relationship status 11778 was healthy; 11784 was suppressed in these sessions.
Compare active health against baseline; don't silently fix unrelated failures.
Update2(False) alone is insufficient: check references, actual gaps, axes,
requested behavior and parent contexts.

```python
old_silent = app.SilentOperation
app.SilentOperation = True
try:
    doc.Save2(False)  # this document, without an automatic dependent-file sweep
finally:
    app.SilentOperation = old_silent
```

Save2 alone is not guaranteed dialog-free; temporary SilentOperation helped
with the primary-view warning. Restore it. Record pre-existing owner changes
in saved documents. Do not SaveAll across dirty unrelated vessels. Updating a
flexible parent may mark it dirty; assess whether its save belongs to the task.

A visible native view supports `view.SaveAsBitmap(absolute_temp_path, width,
height)` for inspection with the image tool. Visibility is not proof of save
or reference resolution. Inspect saved references and reopen when appropriate
without discarding owner work. Embedded filename extraction supports, but does
not replace, native resolution verification.

Use native behavior checks for CAD and current repository gates for software.
The same-session Ruff and 525-test pass was reused for unchanged tooling during
the October 22 CAD work; an old test count does not prove today's tree passes.
If pytest's usual basetemp has Windows permission errors, use a fresh unique
machine-local temp directory rather than deleting or changing permissions on
an unchecked path. Record the actual result.

## Project templates and edge finishing

Use the [PIHTI Inventor templates](../PIHTI%20Templates/README.md) for new
documents. Pass the template path explicitly for automation. Part and assembly
templates use mm, g and s. Use the JIS IDW or DWG template for new drawings.

In a part transaction, select the current solid's exposed edges by geometry.
Add the plan corner rounds first, then select the updated outside perimeter
for the edge break. Verify feature health, overall dimensions, retained
seating and locating faces, and fastener access before saving. Regenerate the
referencing drawing and recheck the assembly positions affected by the edit.

## Mechanical drawing review

Use [JIS B 0001](https://webdesk.jsa.or.jp/books/W11M0090/index/?bunsyo_id=JIS+B+0001%3A2019) for mechanical drawings and its references JIS Z 8311 for sheet layout and JIS Z 8317-1 for dimensioning. Use the repo's A4 metric format. Dimension mating spans directly and use a centerline to show symmetry. Use center marks for drilled patterns and a hatched section where it clarifies depths or seats.

Build drill, tap, counterbore, and countersink patterns with native Inventor Hole features driven by sketch points on the entry face. Check the entry and throat diameters and the cut direction on the solid. Compare the selected screw's seating cone at the intended installed height and test for interference. Actual head diameter at the chamfer is different from the theoretical seat diameter.

### House style from shop-accepted drawings

`Drawings-PDFs/` holds sets that were submitted to the shop and fabricated, made with the same JIS A4 template. Match them. The bellows set shows the before and after: [review](log/2026-11-16-bellows-drawing-shop-readability-review.md), [annotation pass](log/2026-11-16-bellows-drawing-annotation-pass.md), [second pass](log/2026-11-17-bellows-drawing-second-pass.md), [parts sheet](log/2026-11-17-bellows-parts-sheet.md), [subassembly breakdown](log/2026-11-17-bellows-subassembly-breakdown.md).

- The drawing number is the page number, and every sheet heading starts with it: `01   PARTS TO MANUFACTURE`, `04   TABLE PLATE`. A balloon number is the page to turn to, and cross-references read `No. 10`. A purchased part with no drawing of its own takes the number of the page that describes its machining, as the ASH125 wheel tap takes 03. Do not invent prefixes or codes such as `BP-MON` or subassembly letters; the shop cannot decode them. The set name goes on the line below the heading.
- Put one part on each sheet at the largest standard scale that fits. Top left gives the part number and name, then material, thickness for plate parts, and quantity. The title-block name field carries the part name.
- The first sheet is a shaded isometric with balloons and a parts list. Number each part to manufacture with its drawing number. Caption each subassembly view with its plain name and list its parts under the name, such as `FRONT CARRIAGE` over `05, 08 ×2`. The parts table keeps No., Part, Qty, Material and Stock. Each part sheet ends its Qty with where the part goes: `Qty: 6 (2 per carriage)`, `Qty: 2 (bed)`. Kuzmin's purchasing list is a reference sheet at the back, not the cover.
- Name the two parties plainly: **Kuzmin** buys and supplies; **工作室** (the machine shop) supplies stock and machines. Do not write "owner", "shop" or polite business Japanese such as 当方支給 or 御社手配.
- Section views are labelled `A-A ( 2 : 1 )` above the view. The cutting line carries only the letter.
- Every bore, revolved feature, hole pattern and symmetric outline gets a centerline or center mark in plan and in section. The centerline states symmetry; a note does not.
- Dimension geometry on the views. Diameters go on the section; threads are leader notes such as `M3x0.5 - 6H`; chamfers and radii are leader notes such as `C0.5` and `R2`. Give a tolerance only where fit matters and write the limits: `Ø18 h10 (18.00/17.93)`, `Ø45.15 - 45.30`.
- Sheet text is limited to material, thickness, quantity and the occasional office note, in Japanese where it addresses the office. Anything geometric is a dimension.
- The accepted sets carry no revision letters or review status. Long parts and long plates use a break view, keeping both ends at a readable scale. A pattern shows one real pitch and then the full row, e.g. `25`, `60`, `17×60(=1020)`.

### Shop drawing workflow through COM

The bellows pass worked in this order. Each step names the recipe below it.

1. Check that Inventor has PIHTI.ipj active and record the open documents. Open the IDW invisibly; everything it loads is then task-owned. Work each sheet in its own transaction.
2. Fix the template before annotating: cutting-line letters, native view labels, and the part name in the title block ([labels and title block](#labels-and-title-block)).
3. Add centerlines automatically, then symmetry axes after a mirror test ([centerlines](#centerlines)).
4. Replace prose with dimensions and hole notes measured from the geometry. Compare each new value with the prose before deleting it ([dimensions and notes](#dimensions-and-notes)).
5. Break long parts and plates. Rescale to standard scales ([long parts and plates](#long-parts-and-plates)).
6. Build the overview sheet: thin isometric edges, balloons and a parts table ([overview sheet](#overview-sheet)).
7. Run the overlap check and fix what it reports. Save, export a review PDF to scratch, and render every sheet at A4. Repeat until clean ([layout check and verification](#layout-check-and-verification)).
8. Save, re-save if the export dirtied the drawing, and release the documents. Reopen the drawing invisibly to verify it. Export the shop PDF and thin it ([PDF export and publishing](#pdf-export-and-publishing)).

The COM helpers from that pass lived in the session scratch folder and are not committed. The recipes below are what they did.

### Assembly positions for drawings

1. Record the active positional representation, occurrence transforms and the operating constraints. Use a transaction for trial moves. Verify solved positions numerically, then restore the primary pose and constraint limits.
2. In the bellows stage, changing the offset override of a limit-enabled flush constraint left the carriage at its previous position. Two additional flush constraints using the same work-plane proxies fixed the required drawing poses. They are suppressed in Primary. Each drawing representation suppresses the operating travel constraints, enables the fixed-position constraints and supplies their offsets. Test both stage transforms and return to Primary before saving.
3. Pass the representation name as `PositionalRepresentation` in the `AddBaseView` options map. Check each view's `ActivePositionalRepresentation`. Use equal scales and align a fixed model point with `ModelToSheetSpace` when showing two poses. Set an explicit camera up vector and verify the bed is below the clamps in the finished view. Use the model's actual up axis. A transient camera accepted `Eye`, `Target` and `UpVector`; setting the arbitrary orientation enum on the camera failed. Pass the camera to `AddBaseView` with the arbitrary orientation enum instead.
4. Move whole sheets with `d.BrowserPanes.Item("Model").Reorder(targetNode, before, movedNode)`, using `GetBrowserNodeFromObject(sheet)`. It also works on an invisibly opened drawing. Check both `DrawingDocument.Sheets` and the exported PDF. Refer to drawings by their stable IDs so page reordering does not invalidate the shop notes.

### Section views

- Activate the sheet before enumerating annotations. Inventor returned empty collections for some unloaded sheets until activation.
- Place a section sketch on its parent view. Project the measured model point with `ModelToSheetSpace`, then use `SheetToSketchSpace` for the sketch line endpoints. Ground the line and generate the native section. For a short axial detail, the cutting-line length controls the length of the resulting section. Break automatic alignment with `Aligned = False` before positioning a section independently.
- Inspect the actual chord in a section through a shaft flat. If the flat has no specified clocking datum, rotate the displayed section so the flat reads horizontally. Preserve the cut plane and part orientation.
- To move or trim a cutting line, edit `SectionLineSketch`: delete its `GroundConstraint`, call `MoveTo` on the endpoints, add `AddGround` and call `ExitEdit`. Rescaling a parent view scales its cutting lines too, so retrim them afterwards. For an axial section, move only the free end so the section content stays the same.
- Cutting-line letters stay where Inventor puts them: about 1.03 cm to the side of the line and 0.49 cm in from its end. Setting `TextPosition` snaps back. To clear a letter, trim or shift the line, or move the dimensions around it. A cut through a flat may move anywhere along the flat.

### Labels and title block

- The JIS template prints cutting-line letters through `DrawingViewAnnotation.FormattedText`. Its default `<DrawingViewName/> / <DrawingViewSheetName/><DrawingViewSheetIndex/>.<DrawingViewSheetZone/>` renders `A / .` when the section is on its parent's sheet. Set `FormattedText` and `SecondFormattedText` to `<StyleOverride FontSize='0,45'><DrawingViewName/></StyleOverride>`. The decimal comma follows this machine's locale.
- Show native view labels with `ShowLabel = True` and `<StyleOverride FontSize='0,5'><DrawingViewName/>-<DrawingViewName/> ( <DrawingViewScale/> )</StyleOverride>`. Do not type loose label notes. `<DrawingViewScale/>` prints `1,35 : 1` for non-standard scales, so use standard scales. Place a label by testing candidate positions against dimension text and lines, notes, other views and the title block. Prefer above the view; below is acceptable when dimension lines block the space above.
- `<DerivedProperty DerivedID='29708'>` is the sheet name and `29707` the sheet scale. Edit the title block with `TitleBlockDefinition.Edit` (a by-reference sketch output, as in the geometry proxy recipe), replace the text box's `FormattedText` and call `ExitEdit(True)`. Name each sheet `nn Part name`, where `nn` is its page number. Read the result back from a freshly fetched text box.
- Replacing a note's `FormattedText` with plain text drops its `StyleOverride` font size. Carry the override over.

### Centerlines

- `DrawingView.GetAutomatedCenterlineSettings` takes one by-reference output. Set `ApplyToHoles`, `ApplyToCylinders`, `ApplyToRevolutions`, `ProjectionNormalAxis` and `ProjectionParallelAxis`, then pass the object to `SetAutomatedCenterlineSettings`. It returns the created marks and lines. Group center marks by position and delete duplicates of existing marks.
- Add a symmetry axis only after the projected geometry is shown to mirror across it. `DrawingCurves()` also returns stretches of the cutting line outside the part, so clip the start, end and center points to the view box first. Then use `Centerlines.AddBisector` on the two outline edges.
- In a section, `Sheet.Centerlines.AddBisector` with intents on the two parallel bore edges draws the bore axis. A diameter leader and a centerline are separate annotations.

### Dimensions and notes

- Pick curves by model size (`ModelGeometry.Geometry.Radius`) or by projected length divided by the view scale. Use `GeneralDimensions.AddLinear` with center intents (`kCenterPointIntent` = 57860), `AddDiameter` and `AddRadius`. For a diameter measured between section lines, set the text to `Ø<DimensionValue/>`.
- `Text.Origin` is not the centre of the text. Set it, read `Text.RangeBox` and shift by the difference. Text sits about 0.24 cm above its dimension line. Stack levels 0.8 cm apart; text with parentheses is taller. Where the model carries 144.98 for a nominal 145, set `Precision = 0`.
- To add a second arrow to a leader note, use `Leader.RootNode.AddLeader` with an object collection holding the new intent; `Leader.AddLeader` failed. Moving a leader note's `Position` bends the leader, and Inventor then rotated multi-line text vertically. Recreate the note with `LeaderNotes.Add([Point2d text, intent], text)` instead. The text lands on the far side of that point from the arrow. Use `<Br/>` to keep long notes inside the border.
- Use `HoleThreadNotes.Add` when a native Hole and Thread Note is needed. Its default note showed inches on the metric drawing. Pass the JIS metric dimension style, set `UsePartUnits = False` and inspect the note.

### Long parts and plates

- Set the view to a standard scale and call `BreakOperations.Add(84225, start, end, 84481, 3, gap_cm, 1, False)`, with start and end in sheet coordinates. Then retrim the cutting lines.
- In a broken view the outline edges come back as single curves spanning the break. A dimension between two such edges was created and then dropped, so anchor it to their end points (`kStartPointIntent`/`kEndPointIntent`). Map hole positions separately on each side of the break.
- The bellows lead screw went to 1:1 with a break from 110 to 930 mm. The table plate went to 1:2.5 with a break from 170 to 1000 mm, and its thickness moved to the header.

### Overview sheet

- At 1:5–1:20, the 0.5 mm `Visible (ISO)` edges black out shaded assembly views. Copy that layer to `Visible Thin (ISO)` at 0.018 cm and assign it to every `DrawingCurve.Segments(k).Layer` in those views only. About 14,500 segments took 110 s. A model change brings back default-layer edges, so run the pass again after one.
- `curve.ModelGeometry.ContainingOccurrence.Definition.Document.FullFileName` names the part behind each view curve. Attach each balloon to that part's curve nearest the balloon.
- The Monotaro assemblies have the structured BOM view switched off. Native balloons or parts lists would switch it on and dirty the owner's assemblies. Use the drawing-only `BP balloon` sketched symbol: a circle of radius 0.45 cm with eight rim `ConnectionPoint`s, an `InsertionPoint` at the centre and prompted text. Place it with `SketchedSymbols.AddWithLeader([Point2d balloon, GeometryIntent(curve, kMidPointIntent)], 0, 1, prompts)`, where `prompts` is a typed `SAFEARRAY(BSTR)`; a Python list fails. Give the leader a small dot (`ArrowheadType = 71949`). Balloon each part on the view of the subassembly that holds it in the model. A part hidden inside another gets a stacked partner placed with `SketchedSymbols.Add` touching it: 11, the nut, sits beside 14 on the bed view because the model fits it on the lead screw in the bed module, not in the rear carriage.
- Take the per-subassembly counts from the top assembly: group `AllLeafOccurrences` by `OccurrencePath`. A nested subassembly, such as the rear carriage inside the bed module, gets its own list; the parent's list notes `(with rear carriage)` because its view shows it fitted. Assert that the lists sum to the table totals. Keep the lists clear of the shaded geometry; the overlap check does not see view curves.
- `CustomTables.Add` needs typed `SAFEARRAY`s (`VT_ARRAY|VT_BSTR` for titles and contents, `VT_ARRAY|VT_R8` for widths and heights). Inherited 4.5 mm text makes rows wrap, so assign the 3 mm `Table Text Small (JIS)` style. Row gap is set only on the style, so use `Table Compact (JIS)`. Applying a style resets the table title; set `Title` afterwards. Recreate the table rather than adding columns. With 3 mm text these widths hold every row on one line: No. 0.75, Part 4.2, Qty 0.8, Material 2.55, Stock 1.6. Narrower Material or Stock columns wrapped rows to double height. A renumber can rewrite cells in place through `Rows.Item(r).Item(c).Value`, and balloons through `SetPromptResultText(textBox, value)`.

### Layout check and verification

- Overlap check: collect every dimension's `Text.RangeBox`, `DimensionLine` and extension lines, every note box and leader segment, view labels, and the approximate cutting-letter boxes. Report text overlapping text, and text crossed by another object's line. It found what renders alone missed. It does not cover sketched symbols or tables, so check those in the render.
- Render every sheet at A4 after each layout pass. Before reporting, reopen the saved drawing invisibly. Check `ReferenceMissing`, every dimension's and centerline's `Attached`, and the dirty state, then close it.

### PDF export and publishing

- **Save the native drawing before starting the PDF translator.** End the editing transaction and write the changed IDW with `Save2(False)`. Confirm the drawing is clean. In the bellows review, the translator produced a complete PDF but held an internal transaction long enough to block the native save. With a custom table on a sheet, the export left the drawing dirty; save once more afterwards and confirm it is clean before releasing.
- Export all sheets with the PDF translator: `All_Color_AS_Black = 0` for color views, `Remove_Line_Weights = 0` to keep distinct weights, `Vector_Resolution = 400`. Set `SilentOperation = True` around `SaveCopyAs` and never export inside an open transaction. A test export inside a transaction left a modal "Publish Inventor File to DWF" prompt that blocked the COM caller until its Accept button was pressed.
- Tahoma has no Japanese glyphs. In the export, notes and table cells fell back to Malgun Gothic, a Korean font whose shapes for `工作室` match Japanese. For longer Japanese text in a note, set a Japanese font with `<StyleOverride Font='Yu Gothic UI'>…</StyleOverride>`; that rendered correctly in a test export. A font override inside a table cell was not tried.
- Thin the line weights with `pihti-dedup pdf-strokes <export.pdf> <shop.pdf> --pages <first fabrication page>-<last>`; for the current bellows set that is `--pages 4-17`. It applies the [tested width mapping](log/2026-11-16-bellows-centerlines-and-pdf-weights.md), refuses image pages, unknown widths and incremental PDFs, and writes nothing on refusal. Compare the extracted text with the raw export.
- Check for pre-existing and newly opened documents before and after exports. Release task-owned invisible handles and close clean, unreferenced parents first. Closing a parent can release dependencies and invalidate their COM handles, so re-enumerate before acting on the next set. Leave visible, pre-existing or dirty owner documents open.
