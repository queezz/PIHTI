# PIHTI Repository Map

PIHTI is a single Autodesk Inventor project. The repository root—not the parent
`Drawings/` directory—is the project boundary and the workspace selected by
`PIHTI.ipj`.

## Entry points

- `PIHTI.ipj` — active Inventor project; workspace `.`; unique filenames enabled.
- `README.md` — human orientation and operating cautions.
- `INDEX.md` — generated assembly-folder index.
- `AGENTS.md` — agent environment, read order, and invariants.
- `mkdocs.yml` and `docs/` — published documentation.

## Primary engineering trees

- `Plasma Vessel/` — established plasma-chamber assemblies and parts.
- `BoronProbe/` — established boron-probe assemblies and parts.
- `ContentCenter/` — shared reusable and purchased components.
- `PALP/`, `LIBS/`, `Jobin-Yvon/` — probes, diagnostics, and spectroscopy hardware.
- `ElectronicsBox/`, `PCB-boards/` — enclosures and board-related mechanical data.
- `SampleHolder/`, `Scaffolding/`, `Desks/`, `TMP-PT-50/`, `PLD/` — fixtures,
  supports, adapters, and experimental hardware.

## Recent submission trees

- `BoronProbe_2026/` — PR #1 and #3 boron-probe development, including rotating,
  non-bellows, and non-rotating variants.
- `Plasma Vessel_2026/` — PR #1 and #3 system-level integration and local component
  copies. It overlaps substantially with `Plasma Vessel/`.
- `bellows/` — PR #2 bellows clamp/guide submission. Its root contains the likely
  design payload; bundled `Design Data/` and `Templates/` are Pack-and-Go/vendor
  support material, not assumed project source.

These trees are review surfaces, not automatically canonical replacements for
the established folders.

## Fabrication and derived artifacts

- `Drawings-PDFs/` — drawings and PDF exports.
- `3D-printing/` — STL/3MF and related additive-manufacturing outputs.
- `LaserCutting/` — DXF and related cutting outputs.
- `Welding/` — welding-related artifacts.

Derived files may be duplicates of native geometry but can still be useful as
fabrication records.

## Tooling and operational memory

- `pyproject.toml` — install contract for the `pihti-dedup` tool; its version is
  not a CAD archive version.
- `src/pihti_dedup/` — shared scanner, CLI, Flask viewer, templates, and static UI.
- `tests/` — inventory, CLI compatibility, web-route, and version gates.
- `scripts/find_duplicates.py` — compatibility entry point for the earlier
  JSON/CSV/Markdown inventory workflow.
- `scripts/generate_readmes.py` — generated folder navigation.
- `.agents/duplicate-inventory-direction.md` — safe duplicate-review workflow.
- `.agents/dedup-viewer-design.md` — proposed local viewer architecture.
- `.agents/log/` — dated handoffs going forward.
- `.agents/*.json` — durable machine inventories from earlier analyses.

The dated Markdown files directly under `.agents/` are legacy June 2026
handoffs. They remain in place to avoid path churn; new handoffs go in `log/`.

## Excluded or noncanonical areas

- `OldVersions/` — Inventor save history; excluded from normal inventory.
- `staging/` — ignored local intake, reviewed before integration.
- `_site/` — generated MkDocs output.
- `.git/`, caches, and lock files — tooling state.

No sibling folder under the parent `Drawings/` directory is part of PIHTI unless
it is deliberately imported into this repository.
