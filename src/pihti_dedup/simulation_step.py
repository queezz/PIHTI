"""STEP preparation: stable occurrence metadata, display meshes and AP242 exports.
Imported geometry is read-only. Names are keyed by source + named occurrence
path, never OCC/STEP/gmsh entity numbers. Unnamed or duplicate paths cannot be
mapped. OCC converts input geometry to millimetres, and writes millimetres.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path

ROLES = {
    "": "#cbd0d6",
    "cathode": "#a777db",
    "preanode": "#e9b65c",
    "anode": "#e77a71",
    "ground": "#6aa5cb",
    "floating": "#73c0a2",
    "insulator": "#ded4b6",
}
MAP_PATH = Path("simulation/parts.json")
LOCK = threading.RLock()
OCC_LOCK = threading.RLock()


@dataclass
class Part:
    key: str
    original: str
    occurrence: list[str]
    shape: object
    colour: str
    stable: bool = True
    face_colours: list[str | None] = dataclass_field(default_factory=list)


def _name(label):
    from OCP.TDataStd import TDataStd_Name

    attribute = TDataStd_Name()
    return (
        attribute.Get().ToExtString() if label.FindAttribute(attribute.GetID_s(), attribute) else ""
    )


def _document():
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document

    return TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))


def read_parts(path: Path, source: str) -> list[Part]:
    from OCP.collections import Sequence_TDF_Label
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TDF import TDF_Label
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_ColorSurf, XCAFDoc_DocumentTool

    document = _document()
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    reader.SetColorMode(True)
    if reader.ReadFile(str(path)) != IFSelect_RetDone or not reader.Transfer(document):
        raise ValueError("STEP could not be read")
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    colours = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
    roots = Sequence_TDF_Label()
    shapes.GetFreeShapes(roots)
    result = []

    def walk(label, trail, location, stable, depth=0):
        if depth > 64:
            raise ValueError("STEP assembly is too deeply nested")
        referred = TDF_Label()
        reference = shapes.GetReferredShape_s(label, referred)
        definition = referred if reference else label
        placement = location.Multiplied(shapes.GetLocation_s(label)) if reference else location
        original = _name(label) or _name(definition)
        named = bool(original) and not re.fullmatch(r"(?:=>)?[0-9:]+", original)
        occurrence = [*trail, original or "Unnamed part"]
        children = Sequence_TDF_Label()
        shapes.GetComponents_s(definition, children)
        # A writer may wrap a compound part in auto-named SOLID products.
        # Those bodies belong to the named part, not separate CAD occurrences.
        body_wrapper = children.Length() and all(
            _name(_referred(shapes, children.Value(i))).upper() in {"SOLID", "SHELL", "COMPOUND"}
            and _name(children.Value(i)) == original
            for i in range(1, children.Length() + 1)
        )
        if children.Length() and not body_wrapper:
            names = [
                _name(children.Value(i)) or _name(_referred(shapes, children.Value(i)))
                for i in range(1, children.Length() + 1)
            ]
            for i, child_name in enumerate(names, 1):
                walk(
                    children.Value(i),
                    occurrence,
                    placement,
                    stable and named and names.count(child_name) == 1,
                    depth + 1,
                )
            return
        shape = shapes.GetShape_s(definition).Moved(placement)
        if shape.IsNull():
            return
        colour = Quantity_Color()
        found = (
            colours.GetColor_s(label, XCAFDoc_ColorSurf, colour)
            or colours.GetColor_s(label, XCAFDoc_ColorGen, colour)
            or colours.GetColor_s(definition, XCAFDoc_ColorSurf, colour)
            or colours.GetColor_s(definition, XCAFDoc_ColorGen, colour)
        )
        if not found and body_wrapper:
            child = children.Value(1)
            found = colours.GetColor_s(child, XCAFDoc_ColorSurf, colour) or colours.GetColor_s(
                child, XCAFDoc_ColorGen, colour
            )
        if not found:
            from OCP.TopAbs import TopAbs_FACE
            from OCP.TopExp import TopExp_Explorer

            faces = TopExp_Explorer(shapes.GetShape_s(definition), TopAbs_FACE)
            while faces.More() and not found:
                found = colours.GetColor(
                    faces.Current(), XCAFDoc_ColorSurf, colour
                ) or colours.GetColor(faces.Current(), XCAFDoc_ColorGen, colour)
                faces.Next()
        hex_colour = (
            "#{:02x}{:02x}{:02x}".format(
                *[round(v * 255) for v in colour.Values(Quantity_TOC_sRGB)]
            )
            if found
            else ROLES[""]
        )
        # Keep face appearances in topology order, independently of the colour
        # used as the occurrence's editable default.
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopExp import TopExp_Explorer

        face_colours = []
        faces = TopExp_Explorer(shapes.GetShape_s(definition), TopAbs_FACE)
        while faces.More():
            face_colour = Quantity_Color()
            has_colour = colours.GetColor(
                faces.Current(), XCAFDoc_ColorSurf, face_colour
            ) or colours.GetColor(faces.Current(), XCAFDoc_ColorGen, face_colour)
            face_colours.append(
                "#{:02x}{:02x}{:02x}".format(
                    *[round(v * 255) for v in face_colour.Values(Quantity_TOC_sRGB)]
                )
                if has_colour
                else None
            )
            faces.Next()
        key = json.dumps([source, occurrence], ensure_ascii=False, separators=(",", ":"))
        result.append(
            Part(
                key,
                _name(definition) or original,
                occurrence,
                shape,
                hex_colour,
                stable and named,
                face_colours,
            )
        )

    for i in range(1, roots.Length() + 1):
        walk(roots.Value(i), [], TopLoc_Location(), True)
    keys = [part.key for part in result]
    for part in result:
        part.stable = part.stable and keys.count(part.key) == 1
    if not result:
        raise ValueError("STEP contains no shapes")
    return result


def _referred(tool, label):
    from OCP.TDF import TDF_Label

    definition = TDF_Label()
    return definition if tool.GetReferredShape_s(label, definition) else label


def read_map(root):
    path = Path(root) / MAP_PATH
    if not path.exists():
        return {"schema": "pihti-simulation-parts/v1", "parts": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "pihti-simulation-parts/v1" or not isinstance(
        value.get("parts"), dict
    ):
        raise ValueError("unsupported simulation map")
    for entry in value["parts"].values():
        validate(entry)
    return value


def validate(entry):
    if not isinstance(entry, dict) or set(entry) - {"name", "material", "role", "colour"}:
        raise ValueError("invalid part metadata")
    for field in ("name", "material", "role", "colour"):
        if not isinstance(entry.get(field, ""), str) or len(entry.get(field, "")) > 200:
            raise ValueError(f"invalid {field}")
    if not entry.get("name", "").strip() or any(ord(c) < 32 for c in entry["name"]):
        raise ValueError("a part name is required")
    if entry.get("role", "") not in ROLES:
        raise ValueError("unknown electrical role")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", entry.get("colour", "")):
        raise ValueError("colour must have six hexadecimal digits")


def map_revision(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def save_entry(root, key, entry, revision):
    validate(entry)
    with LOCK:
        value = read_map(root)
        if map_revision(value) != revision:
            raise ValueError("The map changed in another window. Reload before saving.")
        value["parts"][key] = entry
        path = Path(root) / MAP_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as stream:
            temp = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        try:
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
        return value


def public_parts(parts, mapping):
    rows = []
    for i, part in enumerate(parts):
        entry = mapping["parts"].get(part.key, {}) if part.stable else {}
        rows.append(
            {
                "id": i,
                "key": part.key,
                "original": part.original,
                "occurrence": part.occurrence,
                "stable": part.stable,
                "mapped": bool(entry),
                "name": entry.get("name", part.original),
                "material": entry.get("material", ""),
                "role": entry.get("role", ""),
                "colour": entry.get("colour", part.colour),
            }
        )
    return rows


def mesh(parts):
    import numpy as np
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    from pihti_dedup.mesh_cache import HEADER, MAGIC, MAX_TRIANGLES, MESH_FORMAT_VERSION

    blocks, ranges, count = [], [], 0
    for part in parts:
        BRepMesh_IncrementalMesh(part.shape, 0.01, False, 0.15, True)
        faces = TopExp_Explorer(part.shape, TopAbs_FACE)
        triangles = []
        appearances, face_index = [], 0
        while faces.More():
            start = len(triangles)
            face = TopoDS.Face(faces.Current())
            location = TopLoc_Location()
            poly = BRep_Tool.Triangulation_s(face, location)
            if poly is not None:
                transform = location.Transformation()
                for index in range(1, poly.NbTriangles() + 1):
                    nodes = list(poly.Triangle(index).Get())
                    if face.Orientation() == TopAbs_REVERSED:
                        nodes.reverse()
                    triangles.append(
                        [
                            [point.X(), point.Y(), point.Z()]
                            for point in [poly.Node(n).Transformed(transform) for n in nodes]
                        ]
                    )
                    if count + len(triangles) > MAX_TRIANGLES:
                        raise ValueError("assembly is too large for the viewer")
            face_colour = (
                part.face_colours[face_index] if face_index < len(part.face_colours) else None
            )
            if len(triangles) > start:
                appearances.append(
                    {
                        "start": (count + start) * 3,
                        "count": (len(triangles) - start) * 3,
                        "colour": face_colour or part.colour,
                    }
                )
            face_index += 1
            faces.Next()
        block = np.asarray(triangles, dtype="<f4").reshape(-1, 3, 3)
        ranges.append({"start": count * 3, "count": len(block) * 3, "appearances": appearances})
        count += len(block)
        blocks.append(block)
    if not count:
        raise ValueError("no renderable faces")
    points = np.concatenate(blocks).reshape(-1, 3)
    data = (
        HEADER.pack(MAGIC, MESH_FORMAT_VERSION, count, *points.min(0), *points.max(0))
        + points.tobytes()
    )
    return data, ranges


def export_bundle(parts, mapping, source, source_hash, strict=False):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TopAbs import TopAbs_COMPOUND
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS_Iterator
    from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_ColorSurf, XCAFDoc_DocumentTool

    rows = public_parts(parts, mapping)
    missing = [row["occurrence"] for row in rows if not row["mapped"]]
    if strict and (missing or any(not row["role"] or not row["material"] for row in rows)):
        raise ValueError("Simulation export needs a saved name, material and role for every part.")
    names = [row["name"] for row in rows]
    # Flat exports give every occurrence its own product identity. A duplicate
    # name is disambiguated by the full authored occurrence path, never an entity number.
    document = _document()
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    colours = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
    emitted = set()
    for part, row in zip(parts, rows, strict=True):
        name = (
            row["name"]
            if names.count(row["name"]) == 1
            else row["name"] + " [" + " / ".join(row["occurrence"]) + "]"
        )
        if name in emitted:
            raise ValueError("duplicate unnamed occurrences need a named Inventor export")
        emitted.add(name)
        row["export_name"] = name
        geometry = part.shape
        while geometry.ShapeType() == TopAbs_COMPOUND:
            iterator = TopoDS_Iterator(geometry)
            if not iterator.More():
                break
            child = iterator.Value()
            iterator.Next()
            if iterator.More():
                break
            geometry = child
        # Isolate underlying topology so repeated occurrences carry independent names/colours.
        world_geometry = BRepBuilderAPI_Transform(
            geometry.Located(TopLoc_Location()), geometry.Location().Transformation(), True
        ).Shape()
        label = shapes.AddShape(world_geometry, False)
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(name))
        channels = [int(row["colour"][i : i + 2], 16) / 255 for i in (1, 3, 5)]
        colour = Quantity_Color(*channels, Quantity_TOC_sRGB)
        colours.SetColor(label, colour, XCAFDoc_ColorGen)
        colours.SetColor(label, colour, XCAFDoc_ColorSurf)
    writer = STEPCAFControl_Writer()
    Interface_Static.SetCVal_s("write.step.schema", "AP242DIS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    if not writer.Transfer(document):
        raise ValueError("STEP export failed")
    with tempfile.TemporaryDirectory(prefix="pihti-step-export-") as scratch:
        target = Path(scratch) / "prepared.step"
        if writer.Write(str(target)) != IFSelect_RetDone:
            raise ValueError("STEP export failed")
        step_bytes = target.read_bytes()
    active = {part.key for part in parts}
    removed = [
        key for key in mapping["parts"] if key not in active and json.loads(key)[0] == source
    ]
    report = {
        "schema": "pihti-simulation-export/v1",
        "source": source,
        "source_sha256": source_hash,
        "map_revision": map_revision(mapping),
        "units": "mm",
        "coordinates": "original world coordinates; no recentering",
        "assembly": "flattened occurrences",
        "parts": rows,
        "unmatched": missing,
        "absent_mapped_parts": removed,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("prepared.step", step_bytes)
        archive.writestr("parts.json", json.dumps(report, ensure_ascii=False, indent=2))
        archive.writestr("mapping.json", json.dumps(mapping, ensure_ascii=False, indent=2))
    return output.getvalue()


def main(argv=None):
    """Repeat a saved mapping on a fresh export without opening the viewer."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("step", type=Path)
    parser.add_argument("source", help="workspace-relative Inventor source used in the viewer")
    parser.add_argument("output", type=Path, help="new ZIP destination; existing files are refused")
    parser.add_argument("--simulation", action="store_true")
    args = parser.parse_args(argv)
    try:
        with OCC_LOCK:
            parts = read_parts(args.step, args.source.replace("\\", "/"))
            data = export_bundle(
                parts,
                read_map(args.workspace),
                args.source.replace("\\", "/"),
                hashlib.sha256(args.step.read_bytes()).hexdigest(),
                args.simulation,
            )
        # Exclusive creation prevents overwriting a source or a previous export.
        with args.output.open("xb") as stream:
            stream.write(data)
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"Prepared {len(parts)} occurrences: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
