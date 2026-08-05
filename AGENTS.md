# AGENTS.md

PIHTI is the curated Autodesk Inventor hardware archive for the PIHTI plasma
system and its probes, vessels, fixtures, electronics, and fabrication outputs.
The repository root is the Inventor workspace; `PIHTI.ipj` is the active project.

Fleet context lives in `C:\Users\queezz\Dropbox\20-Code\fleet`: read its
`RULES.md` and `MAP.md` after the PIHTI-specific files below. Fleet context does
not replace this repository's rules.

## Environment

CAD work does not require Python. The existing documentation commands use the
external `~/.venvs/mkdocs` environment documented in `README.md`.

PIHTI-specific duplicate tooling uses `~/.venvs/pihti-dedup`; never create a
venv in this Dropbox repository. Do not use `~/.venvs/pihti`: that environment
belongs to the separate pihtivacuum application. Install or refresh this project
from the repository root with:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pip install -e ".[dev]"
```

Launch the viewer with `lab pihti`. The shared service declaration lives in the
sibling `20-Code/lab-cli` registry; this machine maps its logical `drawings`
root privately through lab-cli config.

Current gates:

- `& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pytest -q -p
  no:cacheprovider --basetemp "$env:LOCALAPPDATA\Temp\pihti-dedup-pytest"`
- `& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m ruff check src tests
  scripts/find_duplicates.py`
- `git diff --check`
- `~/.venvs/mkdocs/Scripts/mkdocs.exe build --strict` when published docs or
  `mkdocs.yml` change and that environment is available
- a read-only duplicate inventory before any CAD cleanup or staged import

## Read first

1. `README.md`
2. `.agents/README.md`
3. the newest `.agents/log/` entry, when present
4. `.agents/duplicate-inventory-direction.md`
5. fleet `RULES.md` and `MAP.md`

Use `.agents/REPOSITORY_MAP.md` for the folder/boundary map and
`.agents/directions.md` for open work. Shipped milestones belong in
`.agents/CHANGELOG.md`; session evidence belongs in `.agents/log/`.

## Invariants

- Open `PIHTI.ipj` before opening Inventor assemblies or parts.
- The project workspace is `.` and `UsingUniqueFilenames` is `Yes`. Treat a
  repeated CAD filename anywhere in the workspace as an Inventor-resolution
  concern even when the files differ.
- Do not rename or move `.iam`, `.ipt`, `.idw`, `.ipn`, `.stp`, or `.stl` files
  outside Inventor until assembly references have been checked.
- SHA-256 or Git-blob equality proves byte identity only. A different hash may
  mean a real revision, an Inventor resave, or unrelated geometry with a reused
  filename.
- Duplicate tooling proposes and records evidence; it does not silently choose
  the canonical file or rewrite Inventor references.
- Version numbers in `pyproject.toml` and `src/pihti_dedup/__init__.py` describe
  the dedup tool only; they are not versions of the PIHTI CAD archive.
- `OldVersions/`, `_site/`, caches, lock files, local staging, Pack-and-Go logs,
  vendor `Design Data/`, and vendor `Templates/` are not curated source.
- Keep machine-specific paths and student workstation paths out of portable
  documentation and committed manifests.
- Preserve fabrication exports when they are the only surviving artifact, even
  if the native Inventor source is missing.

## Commits and handoffs

Follow `.agents/commit-culture.md`: deliberate path staging, a short imperative
title, and a final `agent: <name>` trailer for agent-authored commits. Never add
`Co-Authored-By`.

After meaningful work, write `.agents/log/YYYY-MM-DD-<kebab>.md` with goal,
decisions, changed paths, verification, and next steps.
