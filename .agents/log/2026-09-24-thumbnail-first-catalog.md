# Thumbnail-first catalog and part page (pihti-dedup 0.15.0)

**Goal:** queezz's live requests, 2026-09-24: pin the tree rail ("not nailed,
hate it"), drop the header furniture, make the catalog visual-first and faster
to navigate, and, through the day's amendments, add a left context rail with an
inspector, tile marks, an instant filter, and a part page on the same shell.

## Decisions

- One shell for `/catalog`, `/catalog/<folder>` and `/part/<path>`: grid
  `25.5rem minmax(0, 1fr) 17rem`, page max 2400px. At 1920px wide that gives a
  408px left rail, a 1141px centre, and a 272px tree rail. The tree rail
  matches the outer Duplicates rail x/width (1608.7-1880.7px). All rails and
  the header line are sticky at `calc(var(--bar-height) + var(--content-pad))`.
- Pinned beats "no inner scrollbar": the tree card and the left rail are capped
  at the viewport minus the sticky offset and the page foot, minus 1px.
  Capping at the full viewport left a 50px end-of-scroll push, measured at a
  700px height. A 0.3px sub-pixel push is absorbed by the 1px.
- `scrollbar-gutter: stable` because short pages moved the rails by 15px.
- The floating hover card was built, then replaced on owner feedback by a
  stationary left-rail inspector. Nothing floats over the grid.
- `PIHTI.ipj` sits in the root rail, not the grid. Folder cards and file tiles
  are separate grids. The folder-card glyph is removed. The header field is a
  filter; Enter is the archive search.
- Tile marks reuse the Duplicates and Doctor hues (edge for copies, dots for
  name problems). "Unused part" was not added because it is too noisy:
  top-level assemblies are legitimately unreferenced.
- Desktop only (1400-2560px). There is one fold below 1200px. Laptop and phone
  layouts are deferred by owner decision.

## Changed paths

`src/pihti_dedup/web.py`, `templates/{catalog,part,_file_tile,_folder_tree
(new),_results,doctor,doctor_name,doctor_assembly}.html`,
`static/dedup.{css,js}`, `tests/test_web.py`, `pyproject.toml`,
`src/pihti_dedup/__init__.py`, `README.md`, `.agents/CHANGELOG.md`,
`.agents/dedup-viewer-design.md`.

## Verification

- pytest 235 passed; ruff clean; `node --check` clean; `git diff --check`
  clean.
- Live DOM on a scratch server (port 48941, since stopped). Rail tops are 84px
  at 0/25/50/75/100% scroll at 1920x1000 and 1920x700, on root, folder, leaf,
  search, and part pages, with the inspector filled. Rail x-positions are
  identical across those pages and Duplicates. A hover prefetch was served
  from the HTTP cache (`transferSize` 0).
- Real workspace through the test client: every preview `src` is versioned;
  a matching `v` gets `immutable` and a wrong one `no-cache`.
  `/catalog/ElectronicsBox` takes 10.6 ms before and 11.6 ms after.

## Next steps

- `dedup.js` still carries the live-note-preview block twice, so each
  keystroke posts twice. This predates the change.
- **Show 48 more** reloads at the top of the list.
- A narrow-window pass if the owner ever wants laptop use.
