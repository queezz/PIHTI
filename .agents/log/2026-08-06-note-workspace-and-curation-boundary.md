# Note editor, workspace label, and curation boundary

**Goal:** make long folder notes usable, restore the English Inventor workspace
label, and establish the safe boundary for catalog organisation.

## Decisions

- Folder-note Markdown now previews live, but rendering never writes a README;
  saving remains the only mutation.
- The dialog is larger and browser-resizable, with independently scrolling
  preview/editor panes and a sticky action row.
- `PIHTI.ipj` keeps workspace path `.` and unique filenames; only its visible
  workspace label is restored to `Workspace`.
- Do not implement a browser-side physical CAD move. A filesystem move would
  change Inventor resolution and therefore needs an Inventor/Design Assistant
  workflow. The next catalog feature should be a reversible virtual curation
  map: principal assembly, attachment relationship, and optional hidden/archive
  drawer, stored separately from CAD paths.

## Changed

- `PIHTI.ipj`
- `src/pihti_dedup/web.py`, `templates/catalog.html`, and static note UI
- version metadata, changelog, and web tests

## State

- `pytest -q -p no:cacheprovider`: 184 passed.
- Ruff and `git diff --check`: clean.

## Next

- Add the virtual curation-map UI after agreeing its small vocabulary and
  persistence location; seed `Plasma Vessel` as the main apparatus and label
  probes/diagnostics as attachments without moving their CAD files.
