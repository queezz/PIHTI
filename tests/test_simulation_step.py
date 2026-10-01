import hashlib
import io
import json
import zipfile

import pytest

from pihti_dedup import simulation_step as prep


def test_map_revision_validation_and_preservation(tmp_path):
    before = prep.read_map(tmp_path)
    key = json.dumps(["assembly.iam", ["assembly", "part:1"]])
    entry = {"name": "Kapton sheet", "material": "Kapton", "role": "insulator", "colour": "#ded4b6"}
    after = prep.save_entry(tmp_path, key, entry, prep.map_revision(before))
    assert prep.read_map(tmp_path) == after
    with pytest.raises(ValueError, match="another window"):
        prep.save_entry(tmp_path, key, entry, prep.map_revision(before))
    with pytest.raises(ValueError, match="colour"):
        prep.save_entry(
            tmp_path, key, {**entry, "colour": "not a colour"}, prep.map_revision(after)
        )
    assert prep.read_map(tmp_path) == after


def fixture_step(path):
    pytest.importorskip("OCP")
    from OCP.BRep import BRep_Builder
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Trsf, gp_Vec
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS_Compound
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    document = prep._document()
    tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    compound = TopoDS_Compound()
    BRep_Builder().MakeCompound(compound)
    assembly = tool.AddShape(compound, True)
    TDataStd_Name.Set_s(assembly, TCollection_ExtendedString("fixture"))
    shape = tool.AddShape(BRepPrimAPI_MakeBox(2, 3, 4).Shape(), False)
    TDataStd_Name.Set_s(shape, TCollection_ExtendedString("mica-sheet"))
    for i in range(2):
        transform = gp_Trsf()
        transform.SetTranslation(gp_Vec(-20 + i * 30, 5, 11))
        component = tool.AddComponent(assembly, shape, TopLoc_Location(transform))
        TDataStd_Name.Set_s(component, TCollection_ExtendedString(f"mica-sheet:{i + 1}"))
    tool.UpdateAssemblies()
    writer = STEPCAFControl_Writer()
    assert writer.Transfer(document)
    writer.Write(str(path))
    return path


def test_named_occurrences_colour_and_geometry_roundtrip(tmp_path):
    path = fixture_step(tmp_path / "original.step")
    before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    parts = prep.read_parts(path, "fixture.iam")
    assert len(parts) == 2 and all(p.stable for p in parts)
    assert parts[0].key != parts[1].key
    data, ranges = prep.mesh(parts)
    mapping = prep.read_map(tmp_path)
    for i, part in enumerate(parts):
        mapping["parts"][part.key] = {
            "name": f"Kapton-{i}",
            "material": "Kapton",
            "role": "insulator",
            "colour": "#33aa77",
        }
    bundle = prep.export_bundle(parts, mapping, "fixture.iam", before_hash, strict=True)
    archive = zipfile.ZipFile(io.BytesIO(bundle))
    report = json.loads(archive.read("parts.json"))
    assert report["units"] == "mm" and report["unmatched"] == []
    output = tmp_path / "roundtrip.step"
    output.write_bytes(archive.read("prepared.step"))
    assert b"AP242" in output.read_bytes()
    restored = prep.read_parts(output, "output.step")
    assert len(restored) == 2
    assert {p.original for p in restored} == {"Kapton-0", "Kapton-1"}
    assert {p.colour for p in restored} == {"#33aa77"}
    from pihti_dedup.mesh_cache import read_header

    _, _, original_box = read_header(data)
    _, _, output_box = read_header(prep.mesh(restored)[0])
    assert output_box == pytest.approx(original_box, abs=1e-5)
    assert original_box == pytest.approx((-20, 5, 11, 12, 8, 15))
    assert len(ranges) == 2 and ranges[1]["start"] > 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_hash
    with pytest.raises(ValueError, match="every part"):
        prep.export_bundle(parts, prep.read_map(tmp_path), "fixture.iam", before_hash, strict=True)


def test_routes_guard_paths_and_stale_edits(tmp_path, step_mirror_folder):
    from pihti_dedup.web import create_app

    original = fixture_step(tmp_path / "fixture.step")
    (tmp_path / "fixture.iam").write_bytes(b"fixture")
    target = step_mirror_folder / "fixture.iam.step"
    target.parent.mkdir(parents=True)
    target.write_bytes(original.read_bytes())
    app = create_app(tmp_path)
    client = app.test_client()
    response = client.get("/simulation")
    assert response.status_code == 200 and b"STEP viewer" in response.data
    assert client.get("/simulation/model?source=../escape.step").status_code == 404
    model = client.get("/simulation/model?source=fixture.iam").get_json()
    part = model["parts"][0]
    payload = {
        "source": "fixture.iam",
        "source_hash": model["source_hash"],
        "revision": model["revision"],
        "key": part["key"],
        "entry": {"name": "Kapton", "material": "Kapton", "role": "insulator", "colour": "#33aa77"},
    }
    assert client.post("/simulation/map", json=payload).status_code == 403
    token = {"X-PIHTI-Token": app.config["FORM_TOKEN"]}
    assert client.post("/simulation/map", json=payload, headers=token).status_code == 200
    assert client.post("/simulation/map", json=payload, headers=token).status_code == 422
    payload["source_hash"] = "stale"
    assert client.post("/simulation/map", json=payload, headers=token).status_code == 409
    assert (
        client.post(
            "/simulation/map",
            json=payload,
            headers=token,
            environ_overrides={"REMOTE_ADDR": "10.0.0.2"},
        ).status_code
        == 403
    )
