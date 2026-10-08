# Folder-focused sourcing workspace

## Goal

Make sourcing options for one design folder easy to switch between, add, read,
and edit in one browser tab. The owner's screenshots showed a full-note stack
on the overview and an editor with no sibling-option navigation.

## Decisions

- Use the existing PIHTI catalog shell and Fleet/paperlib rail vocabulary:
  left rail owns option selection, Find, Add, Save, and return; right rail
  selects the design folder. Shared track widths and resting offsets stay
  unchanged. The attachment's orientation-only packet is context, not a
  restriction on the owner's live implementation request.
- The archive is a compact index grouped by design folder. A folder address
  opens its first option, or a new form when empty. Save stays on the option;
  an originating part remains available through the return link.
- Show name/status/price/supplier/link first. Fold secondary details and the
  searchable CAD checklist. Existing notes lead with rendered content, with
  Write and Split available. Compact reference pictures enlarge in a native
  dialog with arrow navigation, Close, and Escape.
- Keep notes and CAD untouched. The existing conflict, malformed-note, upload,
  localhost, and token guards still apply. Rejected saves remain visibly
  unsaved; navigation invokes the browser's unsaved-change protection.

## Changed

- Sourcing routes, templates, shared sourcing-rail macro, scoped CSS and JS.
- Catalog sourcing summary now opens the folder's sourcing workspace.
- Sourcing navigation/save tests; narrow the existing CSS guard to fixed pixel
  ceilings rather than incorrectly rejecting viewport-relative image dialogs.
- README workflow, both tool-version files (0.33.0), and changelog.

## Verification

- Full declared pytest gate: 520 passed in 44.67 seconds, fresh external
  basetemp, cacheprovider disabled. Ruff, JS syntax, and diff whitespace passed.
- Strict MkDocs build passed; output stayed in external scratch.
- Browser tool preflight and reset failed before execution with Windows sandbox
  setup errors. Misha independently reproduced the failure. Recovered real DOM
  control with bundled Playwright and the installed Brave executable through
  the working owner-context shell; shared the verified recovery with Misha.
- Lab-managed scratch service on an explicitly free port, isolated workspace,
  cache, mirror, runtime, and logs; Inventor session factory disabled.
- Perimeter checks: all eight top tabs, overview/editor internal links,
  Back/Forward, deep reload, catalog anchor clearance, local Find, combined
  status/text filtering, live notes, save/reload, cancelled unsaved navigation,
  add/save, empty-folder selection, CAD checklist/search, attachment upload,
  supplier popup, image Close/Escape/arrows, workspace Escape, and no browser
  page errors. Reading and browsing exercised the detail, overview, disclosures,
  writing modes and image viewer across multiple passes.
- Rail geometry identical across 0/25/50/75/100 percent page scroll at
  1916x1000 and 1400x700: both tops 84px; widths 408px and 272px. No horizontal
  overflow in any notes mode. A 63-option fixture confirmed Find reaches the
  last option and Save/Add remain pinned during internal rail scroll.
- Final screenshots inspected at desktop and short-window sizes. No temporary
  browser code, test data, or generated documentation entered the repository.
- Activated the completed change through the verified real Lab runtime after
  the export batch reported idle; retained its LAN reach. Live health reports
  0.33.0. Stopped the scratch process tree and verified both PIDs gone and its
  listener port free. Scratch scripts/evidence are marked retained.
- After the final thumbnail sizing adjustment, the 30 sourcing/layout/version
  checks passed. Remaining Git dirt is only the pre-existing owner CAD edit.

## Next

Use the folder workspace during actual design and adjust hierarchy from owner
feedback. Existing source notes, including legacy CAD links, were preserved.
The pre-existing modified bellows-probe assembly is outside this tooling commit.

Usage: direct implementation; no child agents. Misha consulted only for the
owner-authorized browser-runtime diagnosis. Provider usage unavailable.
