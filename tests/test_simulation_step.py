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
    assert b'aria-label="STEP folders"' in response.data
    assert b'id="sim-file-find"' in response.data
    assert b'<option value="fixture.iam"' not in response.data
    tile = client.get("/catalog").data
    assert b'data-step-edit="/simulation?source=fixture.iam"' in tile
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
    appearance = client.get("/simulation/model?source=fixture.iam").get_json()
    assert appearance["parts"][0]["colour"] == "#33aa77"
    assert {face["colour"] for face in appearance["parts"][0]["appearances"]} == {"#33aa77"}
    assert appearance["parts"][0]["start"] == 0
    assert appearance["parts"][1]["start"] == appearance["parts"][0]["count"]
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


def test_face_appearances_and_viewport_tessellation(tmp_path):
    pytest.importorskip("OCP")
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool

    document = prep._document()
    tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    colours = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
    shape = BRepPrimAPI_MakeCylinder(10, 20).Shape()
    tool.AddShape(shape, False)
    faces = TopExp_Explorer(shape, TopAbs_FACE)
    expected = ["#ff0000", "#00ff00", "#0000ff"]
    for value in expected:
        channels = [int(value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        colours.SetColor(
            faces.Current(), Quantity_Color(*channels, Quantity_TOC_sRGB), XCAFDoc_ColorSurf
        )
        faces.Next()
    path = tmp_path / "coloured.step"
    writer = STEPCAFControl_Writer()
    assert writer.Transfer(document)
    writer.Write(str(path))
    parts = prep.read_parts(path, "coloured.step")
    data, spans = prep.mesh(parts)
    assert {face["colour"] for face in spans[0]["appearances"]} == set(expected)
    assert sum(face["count"] for face in spans[0]["appearances"]) == spans[0]["count"]
    from pihti_dedup.mesh_cache import read_header

    # A cylinder at the old 0.5-radian setting had visibly polygonal sides.
    assert read_header(data)[1] > 150


def test_solid_colour_inheritance_and_face_override(tmp_path):
    pytest.importorskip("OCP")
    from OCP.BRep import BRep_Builder
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS_Compound
    from OCP.XCAFDoc import XCAFDoc_ColorSurf, XCAFDoc_DocumentTool

    document = prep._document()
    tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    colours = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
    body = BRepPrimAPI_MakeBox(2, 3, 4).Shape()
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    builder.Add(compound, body)
    tool.AddShape(compound, False)
    colours.SetColor(body, Quantity_Color(1, 1, 0, Quantity_TOC_sRGB), XCAFDoc_ColorSurf)
    face = TopExp_Explorer(body, TopAbs_FACE).Current()
    colours.SetColor(face, Quantity_Color(0, 0, 1, Quantity_TOC_sRGB), XCAFDoc_ColorSurf)
    path = tmp_path / "body-colours.step"
    writer = STEPCAFControl_Writer()
    assert writer.Transfer(document)
    writer.Write(str(path))
    parts = prep.read_parts(path, "body-colours.step")
    assert parts[0].face_colours.count("#ffff00") == 5
    assert parts[0].face_colours.count("#0000ff") == 1
    _, ranges = prep.mesh(parts)
    assert {row["colour"] for row in ranges[0]["appearances"]} == {"#ffff00", "#0000ff"}


def test_display_cache_survives_eviction_restart_and_map_edit(tmp_path, monkeypatch):
    from pihti_dedup.web import create_app

    reads = []
    meshes = []

    def parts(path, source):
        reads.append(source)
        return [prep.Part(source, source, [source], object(), "#ff0000")]

    def mesh(value):
        meshes.append(value[0].key)
        return b"cached geometry", [
            {"start": 0, "count": 3, "appearances": [{"start": 0, "count": 3, "colour": "#ff0000"}]}
        ]

    monkeypatch.setattr(prep, "read_parts", parts)
    monkeypatch.setattr(prep, "mesh", mesh)
    for name in ("a.step", "b.step", "c.step"):
        (tmp_path / name).write_text(name)
    client = create_app(tmp_path).test_client()
    first = client.get("/simulation/model?source=a.step")
    assert first.status_code == 200
    for name in ("b.step", "c.step", "a.step"):
        assert client.get("/simulation/model?source=" + name).status_code == 200
    assert reads == meshes == ["a.step", "b.step", "c.step"]
    client = create_app(tmp_path).test_client()
    reused = client.get("/simulation/model?source=a.step")
    assert reused.get_json() == first.get_json()
    assert (
        client.get(
            "/simulation/model?source=a.step", headers={"If-None-Match": reused.headers["ETag"]}
        ).status_code
        == 304
    )
    model = reused.get_json()
    binary = client.get("/simulation/mesh?source=a.step&hash=" + model["source_hash"])
    assert binary.data == b"cached geometry"
    assert "immutable" in binary.headers["Cache-Control"]
    prep.save_entry(
        tmp_path,
        "a.step",
        {"name": "changed", "material": "", "role": "", "colour": "#00ff00"},
        model["revision"],
    )
    changed = client.get("/simulation/model?source=a.step")
    assert changed.get_json()["parts"][0]["appearances"][0]["colour"] == "#00ff00"
    assert changed.headers["ETag"] != reused.headers["ETag"]
    assert len(meshes) == 3
    (tmp_path / "a.step").write_text("new source")
    assert client.get("/simulation/model?source=a.step").status_code == 200
    assert len(meshes) == 4
    assert (
        client.get("/simulation/mesh?source=a.step&hash=" + model["source_hash"]).status_code == 409
    )


def test_oversized_display_refusal_survives_restart(tmp_path, monkeypatch):
    from pihti_dedup import mesh_cache
    from pihti_dedup.web import create_app

    source = tmp_path / "large.step"
    source.write_text("large")
    builds = []
    monkeypatch.setattr(prep, "read_parts", lambda path, source: [])

    def refuse(parts):
        builds.append(1)
        raise ValueError("assembly is too large for the viewer")

    monkeypatch.setattr(prep, "mesh", refuse)
    for _ in range(2):
        client = create_app(tmp_path).test_client()
        assert client.get("/simulation/model?source=large.step").status_code == 422
    assert len(builds) == 1
    monkeypatch.setattr(mesh_cache, "MAX_TRIANGLES", mesh_cache.MAX_TRIANGLES + 1)
    assert client.get("/simulation/model?source=large.step").status_code == 422
    assert len(builds) == 2
    source.write_text("changed large")
    assert client.get("/simulation/model?source=large.step").status_code == 422
    assert len(builds) == 3


def test_background_display_does_not_wait_for_geometry(tmp_path, monkeypatch):
    import threading

    from pihti_dedup.display_worker import DisplayJobs
    from pihti_dedup.web import create_app

    entered, release = threading.Event(), threading.Event()

    def slow(self, source):
        entered.set()
        assert release.wait(5)
        return "STEP display preparation timed out; use the still preview"

    monkeypatch.setattr(DisplayJobs, "_run", slow)
    (tmp_path / "large.step").write_text("synthetic")
    app = create_app(tmp_path, refresh_seconds=60, session_factory=lambda: None)
    try:
        client = app.test_client()
        response = client.get("/simulation/model?source=large.step")
        assert response.status_code == 202 and response.get_json()["pending"]
        assert entered.wait(1)
        # The geometry worker is still blocked: Catalog must finish anyway.
        assert client.get("/catalog").status_code == 200
        assert not release.is_set()
        release.set()
        jobs = app.extensions["pihti_display_jobs"]
        next(iter(jobs.jobs.values())).result(timeout=2)
        assert client.get("/simulation/model?source=large.step").status_code == 422
    finally:
        release.set()
        app.extensions["pihti_display_jobs"].close()


def test_isolated_worker_writes_reusable_geometry(tmp_path):
    import time

    from flask import Flask

    from pihti_dedup.simulation_web import register
    from pihti_dedup.step_mirror import StepMirror

    fixture_step(tmp_path / "worker.step")
    app = Flask(__name__)
    register(app, tmp_path, StepMirror(tmp_path), lambda request: None, background=True)
    try:
        client = app.test_client()
        response = client.get("/simulation/model?source=worker.step")
        assert response.status_code == 202
        deadline = time.monotonic() + 15
        while response.status_code == 202 and time.monotonic() < deadline:
            time.sleep(0.05)
            response = client.get("/simulation/model?source=worker.step")
        assert response.status_code == 200, response.get_json()
        model = response.get_json()
        assert len(model["parts"]) == 2
        assert (
            client.get(
                "/simulation/mesh?source=worker.step&hash=" + model["source_hash"]
            ).status_code
            == 200
        )
    finally:
        app.extensions["pihti_display_jobs"].close()


def test_worker_stop_kills_windows_launcher_tree(monkeypatch):
    from pihti_dedup import display_worker

    class Process:
        pid = 12345

        def poll(self):
            return None

    calls = []
    monkeypatch.setattr(display_worker.sys, "platform", "win32")
    monkeypatch.setattr(display_worker.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(
        display_worker.subprocess, "run", lambda command, **kwargs: calls.append(command)
    )
    display_worker._stop(Process())
    assert calls == [["taskkill", "/PID", "12345", "/T", "/F"]]
