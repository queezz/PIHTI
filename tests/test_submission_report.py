import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from inventor_fake import FakeInventor, fake_session, reference_bytes

from pihti_dedup import cli
from pihti_dedup.submission_report import inspect_submission, render_report, report_status


def workspace(tmp_path: Path, *, owner_open=()):
    (tmp_path / "PIHTI.ipj").write_bytes(b"")
    folder = tmp_path / "Submission"
    folder.mkdir()
    assembly = folder / "probe.iam"
    drawing = folder / "probe.idw"
    assembly.write_bytes(reference_bytes("old-fossil.ipt"))
    drawing.write_bytes(b"drawing")
    missing = tmp_path.parent / "private-student-folder" / "missing.ipt"
    app = FakeInventor({assembly: [], drawing: [missing]}, owner_open=owner_open)
    app.SilentOperation = False
    app.DesignProjectManager = SimpleNamespace(
        ActiveDesignProject=SimpleNamespace(FullFileName=str(tmp_path / "PIHTI.ipj"))
    )
    return app


def test_native_report_includes_drawings_and_excludes_fossil_strings(tmp_path):
    app = workspace(tmp_path)
    report = inspect_submission(tmp_path, "Submission", fake_session(app))
    text = render_report(report)
    assert report_status(report) == 1
    assert "missing.ipt" in text and "probe.idw" in text
    assert "old-fossil" not in text and "private-student-folder" not in text
    assert app.ours() == []
    assert not app.SilentOperation
    assert not any(row[0] in {"save", "replace", "saveas"} for row in app.log)


def test_owner_open_document_makes_report_incomplete_without_closing_it(tmp_path):
    app = workspace(tmp_path, owner_open=[tmp_path / "Submission" / "probe.iam"])
    report = inspect_submission(tmp_path, "Submission", fake_session(app))
    assert report_status(report) == 2
    assert "Close this document" in render_report(report)
    assert not app.violations


def test_wrong_project_and_outside_folder_are_refused(tmp_path):
    app = workspace(tmp_path)
    with pytest.raises(ValueError, match="inside"):
        inspect_submission(tmp_path, "..", fake_session(app))
    app.DesignProjectManager.ActiveDesignProject.FullFileName = "other.ipj"
    with pytest.raises(ValueError, match="PIHTI.ipj"):
        inspect_submission(tmp_path, "Submission", fake_session(app))
    assert app.log == []


def test_cli_requires_inventor_instead_of_certifying_static_strings(tmp_path, monkeypatch, capsys):
    workspace(tmp_path)
    monkeypatch.setattr(cli.inventor_session, "connect", lambda: None)
    assert cli.main(["submission-report", str(tmp_path), "--folder", "Submission"]) == 2
    assert "Start Inventor" in capsys.readouterr().err


def test_external_dependencies_are_reported_without_exposing_machine_paths(tmp_path):
    app = workspace(tmp_path)
    external = tmp_path.parent / "vendor.ipt"
    external.write_bytes(b"vendor")
    app.disk[next(key for key in app.disk if key.endswith("probe.idw"))] = [str(external)]
    report = inspect_submission(tmp_path, "Submission", fake_session(app))
    findings = next(d for d in report["documents"] if d["path"].endswith(".idw"))["findings"]
    assert findings == [{"name": "vendor.ipt", "kind": "external", "workspace_candidates": []}]
    assert str(tmp_path.parent) not in render_report(report)


def test_cli_writes_portable_issue_checklist_and_native_evidence(tmp_path, monkeypatch):
    app = workspace(tmp_path)
    monkeypatch.setattr(cli.inventor_session, "connect", lambda: fake_session(app))
    markdown = tmp_path / "request.md"
    evidence = tmp_path / "request.json"
    assert cli.main(
        [
            "submission-report", str(tmp_path), "--folder", "Submission",
            "--markdown", str(markdown), "--json", str(evidence),
        ]
    ) == 1
    assert "- [ ] Supply or repair" in markdown.read_text(encoding="utf-8")
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["schema"] == "pihti-submission-report/v1"
    assert str(tmp_path.parent) not in evidence.read_text(encoding="utf-8")
