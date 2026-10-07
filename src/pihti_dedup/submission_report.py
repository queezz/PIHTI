"""Read-only native dependency reports suitable for a submission issue or PR."""

from __future__ import annotations

import ntpath
from pathlib import Path

from pihti_dedup.inventor_session import (
    Session,
    SessionTimeout,
    _close,
    _open_paths,
    _open_skipping_unresolved,
    path_key,
)
from pihti_dedup.inventory import scan_workspace
from pihti_dedup.whereused import filename_locations


def inspect_submission(root: Path, folder: str, session: Session) -> dict:
    """Inspect saved IAM/IDW/IPN files, never save or replace references."""
    root = root.resolve()
    if not folder.strip():
        raise ValueError("Enter the submission folder; use '.' explicitly to check the entire workspace.")
    target = (root / folder).resolve()
    if not target.is_relative_to(root) or not target.is_dir():
        raise ValueError("Choose a folder inside the Inventor workspace.")
    inventory = scan_workspace(root, hash_files=False)
    paths = [
        root / record.path
        for record in inventory.records
        if Path(record.path).suffix.casefold() in {".iam", ".idw", ".ipn"}
        and (root / record.path).is_relative_to(target)
    ]
    if not paths:
        raise ValueError("The folder contains no in-scope assemblies, drawings or presentations.")
    locations = filename_locations(root)

    def project(application, run):
        active = application.DesignProjectManager.ActiveDesignProject.FullFileName
        if path_key(active) != path_key(root / "PIHTI.ipj"):
            raise ValueError("Open PIHTI.ipj in Inventor before checking a submission.")

    session.run(project)
    documents = []
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix()

        def inspect(application, run, path=path, relative=relative):
            if path_key(path) in _open_paths(application, run):
                return {"path": relative, "error": "Close this document in Inventor, then rerun."}
            document = None
            try:
                document = _open_skipping_unresolved(application, path)
                references = document.File.ReferencedFileDescriptors
                findings = []
                for index in range(1, references.Count + 1):
                    descriptor = references.Item(index)
                    full = str(descriptor.FullFileName)
                    name = ntpath.basename(full)
                    missing = bool(descriptor.ReferenceMissing)
                    if not missing and Path(full).resolve().is_relative_to(root):
                        continue
                    findings.append(
                        {
                            "name": name,
                            "kind": "missing" if missing else "external",
                            "workspace_candidates": list(locations.get(name.casefold(), ())),
                        }
                    )
                    run.tick()
                return {"path": relative, "findings": findings}
            except Exception as exc:
                return {"path": relative, "error": f"Inventor inspection failed ({type(exc).__name__})."}
            finally:
                if document is not None:
                    _close(document)

        try:
            documents.append(session.run(inspect, timeout=20))
        except SessionTimeout:
            documents.append({"path": relative, "error": "Inventor stopped responding; check its dialogs."})
            break
    return {
        "schema": "pihti-submission-report/v1",
        "folder": target.relative_to(root).as_posix(),
        "inventor": session.version,
        "expected_documents": len(paths),
        "inventory_complete": not inventory.errors,
        "documents": documents,
    }


def report_status(report: dict) -> int:
    if not report["inventory_complete"] or len(report["documents"]) != report["expected_documents"] or any(
        document.get("error") for document in report["documents"]
    ):
        return 2
    return int(any(document["findings"] for document in report["documents"]))


def render_report(report: dict) -> str:
    lines = [
        "# CAD submission dependency check",
        "",
        f"Folder: `{report['folder']}`. Inventor: `{report['inventor']}`.",
        "Checks saved assemblies, drawings and presentations; no CAD changes were made.",
        "",
        "## Requested corrections",
        "",
    ]
    for document in report["documents"]:
        if document.get("error"):
            lines.append(f"- [ ] `{document['path']}`: {document['error']}")
        for finding in document.get("findings", ()):
            action = "Supply or repair the link to" if finding["kind"] == "missing" else "Include or document the external dependency"
            lines.append(f"- [ ] {action} `{finding['name']}` in `{document['path']}`.")
            if finding["workspace_candidates"]:
                lines.append("  Same-name workspace candidates (verify the intended file in Inventor):")
                lines.extend(f"  - `{path}`" for path in finding["workspace_candidates"])
    status = report_status(report)
    if status == 0:
        lines.append("No missing or external direct dependencies found in the checked documents.")
    elif status == 2:
        lines.append("\nInspection is incomplete; this report does not certify the submission.")
    lines.extend(
        [
            "",
            "## How to respond",
            "",
            "Provide the dependency files in a follow-up PR or attach a Pack-and-Go ZIP to the issue.",
            "Use workspace-relative paths and list reused archive/library components. Do not rename CAD outside Inventor.",
            "If a dependency was renamed or intentionally superseded, explain the replacement and update the referring documents through Inventor.",
            "Reopen saved deliverables under PIHTI.ipj, rerun this check and attach the new report before closing the request.",
            "A clean report checks dependency presence, not whether a same-name part is the correct revision or geometry.",
            "",
        ]
    )
    return "\n".join(lines)
