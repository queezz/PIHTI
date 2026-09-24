"""Read-only lint for folder notes and sidecars: `pihti-dedup notes check`.

A visual pass (`.agents/visual-pass.md`) turns the owner's narration into a
folder's `README.md` and a file's sidecar. Both are hand-edited Markdown, so
both can drift: a generated note can be hand-edited without going through
`foldernote.write_folder_note` (which is what strips the generator marker),
an authored note can lose its summary sentence, and a sidecar can end up with
frontmatter the tool refuses to parse. A sourcing note (`<folder>/sourcing/
*.md`) is hand-editable too. This module finds the four drifts and reports
them; it never writes anything.

1. **Marker on an authored note** — either the generator marker survived
   somewhere in a note that is otherwise hand-written prose, or the marker is
   still the note's first line while a person has added prose above the
   generated sections (a hand edit that skipped
   `foldernote.strip_autogen_marker`).
2. **Authored note without a summary sentence** — a marker-free `README.md`
   whose first line after the title is structure (heading, list, blockquote,
   code fence) rather than the one prose sentence `note_excerpt` and the
   catalog card depend on.
3. **Sidecar that does not parse** — `sidecar.read_sidecar` raises on the
   file, or its `hero` key is present but not a boolean.
4. **Sourcing note that does not parse** — `sourcing.parse_option` refuses
   it: the frontmatter is not readable, or its `status` is not one of
   `candidate`, `quoted`, `ordered`, `received`, `rejected` (or another key
   has the wrong shape).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Sequence

from pihti_dedup.foldernote import AUTOGEN_MARKER, FolderNoteError, is_generated, read_folder_note
from pihti_dedup.geometry_preview import GEOMETRY_EXTENSIONS
from pihti_dedup.inventor_meta import INVENTOR_EXTENSIONS
from pihti_dedup.inventory import FileRecord, scan_workspace
from pihti_dedup.sidecar import SidecarError, read_sidecar, sidecar_path
from pihti_dedup.sourcing import is_sourcing_path, read_folder_options, sourcing_dir

#: Extensions a sidecar can meaningfully sit beside: Inventor's own OLE
#: documents plus the geometry/export formats the catalog can preview.
SIDECAR_EXTENSIONS = INVENTOR_EXTENSIONS | GEOMETRY_EXTENSIONS

_TITLE_PREFIX = "# "
_GENERATED_HEADING_PREFIX = "## "
# Both generator variants: the folder inventory and ContentCenter's category index.
_GENERATED_NOTICE_PREFIXES = ("> Generated CAD inventory", "> Auto-generated index")
# A folder-note line here is structure, not the summary sentence a card excerpt
# needs — mirrors `foldernote._SKIP_PREFIXES` minus the marker/table cases that
# do not apply to "the first line after the title".
_STRUCTURAL_PREFIXES = ("#", ">", "-", "*", "```")

MARKER = "marker"
SUMMARY = "summary"
SIDECAR = "sidecar"
SOURCING = "sourcing"
CATEGORY_ORDER = (MARKER, SUMMARY, SIDECAR, SOURCING)
CATEGORY_TITLES = {
    MARKER: "Marker on an authored note",
    SUMMARY: "Authored note without a summary sentence",
    SIDECAR: "Sidecar that does not parse",
    SOURCING: "Sourcing note that does not parse",
}


@dataclass(frozen=True)
class Finding:
    category: str
    path: str
    detail: str


@dataclass(frozen=True)
class CheckResult:
    findings: tuple[Finding, ...]

    @property
    def clean(self) -> bool:
        return not self.findings

    def in_category(self, category: str) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if finding.category == category)


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _folders(records: Sequence[FileRecord]) -> list[str]:
    """Distinct parent folders of `records`, plus the workspace root `"."`."""

    found = {"."}
    for record in records:
        found.add(str(PurePosixPath(record.path).parent))
    return sorted(found)


def _has_authored_prose_above_sections(text: str) -> bool:
    """True when hand-written prose sits above the generator's own sections.

    Walks lines from the top, stopping at the first generated `## ` heading.
    Blank lines, the marker's own comment lines, the `# Title`, and the
    generated notice blockquote are all expected scaffolding; anything else
    seen before that heading is a person's own words left on the wrong side
    of the still-present marker.
    """

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(_GENERATED_HEADING_PREFIX):
            return False
        if not line:
            continue
        if line.startswith("<!--"):
            continue
        if line.startswith(_TITLE_PREFIX):
            continue
        if line.startswith(_GENERATED_NOTICE_PREFIXES):
            continue
        return True
    return False


def _missing_summary_sentence(text: str) -> bool:
    """True when the first line after the title is not a prose sentence."""

    non_blank = [line.strip() for line in text.splitlines() if line.strip()]
    if not non_blank:
        return True
    index = 1 if non_blank[0].startswith(_TITLE_PREFIX) else 0
    if index >= len(non_blank):
        return True
    return non_blank[index].startswith(_STRUCTURAL_PREFIXES)


def _folder_note_findings(root: Path, folders: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    for folder in folders:
        folder_path = root if folder == "." else root / folder
        try:
            note = read_folder_note(folder_path)
        except FolderNoteError:
            continue
        if note is None:
            continue
        rel = _relative(root, note.path)
        text = note.text
        generated_first_line = is_generated(text)
        marker_anywhere = any(line.strip() == AUTOGEN_MARKER for line in text.splitlines())
        if not generated_first_line and marker_anywhere:
            findings.append(
                Finding(
                    MARKER,
                    rel,
                    "the generator marker survives inside an otherwise authored note",
                )
            )
        elif generated_first_line and _has_authored_prose_above_sections(text):
            findings.append(
                Finding(
                    MARKER,
                    rel,
                    "authored prose sits above the generated sections, ahead of the marker",
                )
            )
        if not generated_first_line and _missing_summary_sentence(text):
            findings.append(
                Finding(SUMMARY, rel, "no prose sentence directly under the title")
            )
    return findings


def _sidecar_findings(root: Path, records: Sequence[FileRecord]) -> list[Finding]:
    findings: list[Finding] = []
    for record in records:
        if Path(record.path).suffix.casefold() not in SIDECAR_EXTENSIONS:
            continue
        path = sidecar_path(root / record.path)
        if not path.exists():
            continue
        rel = _relative(root, path)
        try:
            sidecar = read_sidecar(path)
        except (SidecarError, UnicodeDecodeError, OSError) as exc:
            detail = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
            findings.append(Finding(SIDECAR, rel, detail))
            continue
        if sidecar is None:
            continue
        hero = sidecar.frontmatter.get("hero")
        if hero not in (None, "", True, False):
            findings.append(Finding(SIDECAR, rel, "hero must be true or false"))
    return findings


def _sourcing_findings(root: Path, folders: Sequence[str]) -> list[Finding]:
    """Every sourcing note under a scanned folder or any of its ancestors."""

    candidates: set[str] = set()
    for folder in folders:
        parts = PurePosixPath(folder).parts
        for depth in range(1, len(parts) + 1):
            candidates.add("/".join(parts[:depth]))
    findings: list[Finding] = []
    for folder in sorted(candidates, key=str.casefold):
        if folder == "." or is_sourcing_path(folder):
            continue
        path = root / folder
        if not sourcing_dir(path).is_dir():
            continue
        _options, problems = read_folder_options(path, folder)
        findings.extend(
            Finding(SOURCING, problem.relative_path, problem.detail) for problem in problems
        )
    return findings


def check_notes(root: Path) -> CheckResult:
    """Read-only lint over `root`'s folder notes and sidecars.

    Walks the same scope the catalog scans (`scan_workspace` with vendor
    payloads excluded, no hashing) so this only reports on paths a visual
    pass would actually touch.
    """

    inventory = scan_workspace(root, include_vendor=False, hash_files=False)
    folders = _folders(inventory.records)
    findings = (
        _folder_note_findings(root, folders)
        + _sidecar_findings(root, inventory.records)
        + _sourcing_findings(root, folders)
    )
    findings.sort(key=lambda finding: (CATEGORY_ORDER.index(finding.category), finding.path.casefold()))
    return CheckResult(tuple(findings))
