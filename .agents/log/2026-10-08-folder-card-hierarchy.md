# Restore folder-card hierarchy

## Goal

Correct the previous oversized sourcing treatment. The folder's description
must dominate its navigation controls. The owner also requested visual separation.

## Decisions and changed paths

- Keep the description and existing full-note button in the folder card; increase
  the overview's text size for comfortable reading.
- Put Sourcing and Brainstorm board in a separate compact card below the folder
  card. Neutral button styling and an inline option count replace the large filled
  call to action, separate status line and extra Add button. Add remains inside
  the sourcing workspace.
- Preserve the full note reader/editor, save and close behavior and shared rail
  widths. Recovered rail space belongs to the inspector.
- Change catalog template/context, CSS, existing sourcing route assertions,
  README and version pair; record tool patch 0.34.2 in the changelog. No CAD edits.

## Verification

- Full suite: 522 passed; affected sourcing/web suite repeated after the final
  card separation. Ruff, strict MkDocs and whitespace checks passed.
- Isolated Lab fixture with its own workspace, cache, mirror and runtime:
  browser at 1916×1000 and 1400×700. Confirmed the sourcing card sits below the
  folder card and is less than one third of its height; checked source/board links,
  note view/edit/read/close, back/forward/reload, empty folders and all top tabs.
  Inspected screenshots, no horizontal overflow or browser errors.
- Verified owner runtime/listener and idle export state before Lab restart;
  preserved LAN reach and stopped the temporary service after checks.

## Next steps

Use the smaller navigation card while browsing real folders. Full-note reading
continues through the established modal, not through rail prose.

Provider usage: unavailable. Child-agent count: 0.
