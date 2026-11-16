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

Place section lines through the actual feature centers and constrain the line in the parent view sketch. Keep arrows, labels, dimension text, and leaders clear of one another. Check the native drawing after model regeneration for detached dimensions. Review every affected sheet at A4 before issuing fabrication files.

### House style from shop-accepted drawings

`Drawings-PDFs/` holds sets that were submitted to the shop and fabricated, made with the same JIS A4 template. Match them. Do not copy the prose-heavy style of the 2026-11 bellows set ([review](log/2026-11-16-bellows-drawing-shop-readability-review.md)).

- Put one part on each sheet at the largest standard scale that fits. Top left gives the circled item number and part name, then material (`SUS`, `A5052`), thickness for plate parts and quantity (`Amount: 3 items`). The title-block name field carries the part name.
- The first sheet is a shaded isometric with balloons and a native parts list (ITEM, QTY, PART NUMBER) plus one material line. It carries no assembly prose.
- Section views are labelled `A-A ( 2 : 1 )` above the view. The cutting line carries only the letter.
- Every bore, revolved feature, hole pattern and symmetric outline gets a centerline or center mark in plan and in section. The centerline states symmetry; a note does not.
- Dimension geometry on the views. Diameters go on the section; threads are leader notes such as `M3x0.5 - 6H`; chamfers and radii are leader notes such as `C0.5` and `R2`. Give a tolerance only where fit matters and write the limits: `Ø18 h10 (18.00/17.93)`, `Ø45.15 - 45.30`.
- Sheet text is limited to material, thickness, quantity and the occasional office note, in Japanese where it addresses the office. Anything geometric is a dimension.
- The accepted sets carry no revision letters or review status. Long parts use a break view with end details rather than full-length views at tiny scale.

### Assembly positions for drawings

1. Record the active positional representation, occurrence transforms and the operating constraints. Use a transaction for trial moves. Verify solved positions numerically, then restore the primary pose and constraint limits.
2. In the bellows stage, changing the offset override of a limit-enabled flush constraint left the carriage at its previous position. Two additional flush constraints using the same work-plane proxies fixed the required drawing poses. They are suppressed in Primary. Each drawing representation suppresses the operating travel constraints, enables the fixed-position constraints and supplies their offsets. Test both stage transforms and return to Primary before saving.
3. Pass the representation name as `PositionalRepresentation` in the `AddBaseView` options map. Check each view's `ActivePositionalRepresentation`. Use equal scales and align a fixed model point with `ModelToSheetSpace` when showing two poses. Set an explicit camera up vector and verify the bed is below the clamps in the finished view. Use the model's actual up axis. A transient camera accepted `Eye`, `Target` and `UpVector`; setting the arbitrary orientation enum on the camera failed. Pass the camera to `AddBaseView` with the arbitrary orientation enum instead.
4. Use `BrowserPane.Reorder` on the drawing's Model browser nodes to move whole sheets. Check both `DrawingDocument.Sheets` and the exported PDF. Refer to drawings by their stable IDs so page reordering does not invalidate the shop notes.

### Section views and bore centerlines

- Activate the sheet before enumerating annotations. Inventor returned empty collections for some unloaded sheets until activation. Restore the starting sheet after inspection.
- Place a section sketch on its parent view. Project the measured model point with `ModelToSheetSpace`, then use `SheetToSketchSpace` for the sketch line endpoints. Ground the line and generate the native section. For a short axial detail, the cutting-line length controls the length of the resulting section. Break automatic alignment with `Aligned = False` before positioning a section independently.
- A diameter leader and a dash-dot centerline are separate annotations. Attach a diameter or hole callout to the circular edge. In the section, use `Sheet.Centerlines.AddBisector` with geometry intents on the two parallel bore edges. Verify the bisected axis and its layer. Extend the endpoints enough for the dash pattern to show while leaving clearance to dimensions. The bellows sections used the existing Centerline (ISO) layer.
- Inspect the actual chord in a section through a shaft flat. If the flat has no specified clocking datum, rotate the displayed section so the flat reads horizontally. Preserve the cut plane and part orientation. Attach the set-screw leader to the flat edge and verify it after rotating the view.
- Use `HoleThreadNotes.Add` when a native Hole and Thread Note is needed. Inventor accepted eligible extruded bores. Its default note showed inches even though the drawing dimensions were metric. Pass the JIS metric dimension style, set `UsePartUnits = False` and inspect the displayed note before relying on it. This option is independent of the centerline.

### Annotation pass through COM

These recipes were verified on the bellows set on 2026-11-16. See the [annotation pass log](log/2026-11-16-bellows-drawing-annotation-pass.md).

- **Section-line letters.** The JIS template prints the cutting-line letters through `DrawingViewAnnotation.FormattedText`. The default `<DrawingViewName/> / <DrawingViewSheetName/><DrawingViewSheetIndex/>.<DrawingViewSheetZone/>` renders `A / .` when the section is on the same sheet as its parent. Set `FormattedText` and `SecondFormattedText` to `<StyleOverride FontSize='0,45'><DrawingViewName/></StyleOverride>`. Its decimal comma follows this machine's locale, the same as the title-block XML.
- **View labels.** Show the native label with `ShowLabel = True` and format it as `<StyleOverride FontSize='0,5'><DrawingViewName/>-<DrawingViewName/> ( <DrawingViewScale/> )</StyleOverride>`. Do not type loose label notes. `<DrawingViewScale/>` prints `1,35 : 1` for non-standard scales, so set views to standard scales instead. To place a label, test candidate positions against each dimension's `Text.RangeBox` and `DimensionLine`, against notes, other views and the title block. Prefer above the view. Below the view is acceptable when dimension lines block the space above.
- **Part name in the title block.** `<DerivedProperty DerivedID='29708'>` is the sheet name; `29707` is the sheet scale. Edit the definition with `TitleBlockDefinition.Edit` (a by-reference sketch output, as in the geometry proxy recipe), replace the text box's `FormattedText`, and call `ExitEdit(True)`. Name each sheet `BP-MON-xx Part name`. Read the result back from a freshly fetched text box.
- **Automated centerlines.** `DrawingView.GetAutomatedCenterlineSettings` takes one by-reference output. Set `ApplyToHoles`, `ApplyToCylinders`, `ApplyToRevolutions`, `ProjectionNormalAxis` and `ProjectionParallelAxis`, then pass the object to `SetAutomatedCenterlineSettings`. It returns the created marks and lines. Group the center marks by position and delete any duplicate of an existing mark. This added section bore axes, which Codex had omitted, without duplicating its hand-placed marks.
- **Symmetry axes.** Add a centerline only after the projected geometry is shown to mirror across it. `DrawingCurves()` also returns stretches of the cutting line outside the part, so clip the start, end and center points to the view box first. Then use `Centerlines.AddBisector` on the two outline edges.
- **Dimensions from prose.** Pick curves by model size from `ModelGeometry.Geometry.Radius` or by projected length divided by the view scale. Use `GeneralDimensions.AddLinear` with center intents (`kCenterPointIntent` = 57860), `AddDiameter` and `AddRadius`. For a diameter measured between section lines, set the text to `Ø<DimensionValue/>`. Compare every returned value with the prose before deleting the prose.
- **Leader notes.** To add a second arrow, use `Leader.RootNode.AddLeader` with an object collection holding the new intent; `Leader.AddLeader` failed. Moving a leader note's `Position` bends the leader, and Inventor then rotated multi-line text vertically. Recreate the note instead with `LeaderNotes.Add([Point2d text, intent], text)`. The text lands on the far side of that point from the arrow. Use `<Br/>` to keep long notes inside the border.
- **Long shafts.** Set the view to 1:1 and call `BreakOperations.Add(84225, start, end, 84481, 3, gap_cm, 1, False)` with the start and end in sheet coordinates. A scale change also scales the section-line sketches. Retrim them inside `SectionLineSketch.Edit`: delete the `GroundConstraint`, call `MoveTo` on the endpoints, add `AddGround` and call `ExitEdit`. For an axial section, move only the free end so the section content stays the same.
- **Verify.** Save, export a review PDF to a scratch folder, and render every sheet at A4. Before reporting, reopen the saved drawing invisibly. Check `ReferenceMissing`, every dimension's and centerline's `Attached`, and the dirty state, then close it.

### PDF export and publishing

- **Save the native drawing before starting the PDF translator.** End the editing transaction and write the changed IDW with `Save2(False)`. Check the file save counter or the timestamp and confirm the drawing is clean. In the bellows review, the translator produced a complete PDF but held an internal transaction long enough to block the native save.
- Export all sheets using the PDF translator and set `All_Color_AS_Black = 0` for color views. `Remove_Line_Weights = 1` makes the strokes uniform. Keep it at 0 when the shop set needs distinct weights for outlines, dimensions and centerlines.
- When the exporter draws small holes too heavily, run `pihti-dedup pdf-strokes <export.pdf> <shop.pdf> --pages 5-17` on the saved export. It applies the mapping below, refuses image pages, unknown widths and incremental PDFs, and writes nothing on refusal. The background: on the bellows fabrication pages, the PDF used standalone width operators at the start of content-stream lines, sometimes followed by other operators. A bounded rewrite changed only the six observed stroke widths. Verify the matched count against parsed PDF `w` operators, reject unexpected widths or embedded graphics on the pages being remapped, and compare the unchanged content, page boxes and extracted text. Keep the cover and color assembly views as exported. Render the table-plate holes and section centerlines at A4 to verify legibility. See the [tested width mapping](log/2026-11-16-bellows-centerlines-and-pdf-weights.md).
- Check for pre-existing and newly opened documents before and after visual exports. Release task-owned invisible handles and close clean, unreferenced parents first. Closing a parent can release dependencies and invalidate their COM handles, so re-enumerate before acting on the next set. Leave visible, pre-existing or dirty owner documents open.
