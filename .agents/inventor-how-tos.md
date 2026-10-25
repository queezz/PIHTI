# Inventor automation how-tos

Verified with running Inventor 2027.1 during October 8–22, 2026. These recipes
supplement AGENTS.md. Old occurrence names, face indices and dimensions must
be checked against current geometry, not copied blindly into an edited model.

## Working preference and starting checks

Queezz prefers background COM work over mouse/keyboard automation. Use the
existing external `~/.venvs/pihti-dedup` Python environment and its `comtypes`.
Read the available Computer Use skill before Windows automation, as required
by that skill. Do not create a repository venv for CAD work.

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
