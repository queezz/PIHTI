# Folder overview and sourcing visibility

## Goal and owner clarification

Make sourcing easy to find in the folder card and replace the mostly clipped
Markdown preview with a useful brief overview. The owner explicitly retained
the existing one-click note reader, Edit toggle and one-click return. Full
Markdown does not belong in the rail; a short overview does.

## Decisions and changed paths

- Folder cards show the first authored paragraph as plain text, up to 240
  characters, using the existing excerpt helper. No Markdown headings, details,
  generated inventory or fade overlay competes with that overview.
- Preserve the existing Read the whole note / Write one buttons and all modal
  reader, editor, save and close behavior. No full note section in the main grid.
- Add a prominent full-width Open sourcing action, option summary and direct
  Brainstorm board / Add option actions. Remove the old tiny corner links and
  fixed card budget that could clip those controls.
- Changed catalog template and its context, CSS, root-description clipping
  selector/comment, affected existing regression assertions, README, version
  pair and changelog. Tool patch version 0.34.1. No CAD or folder note edits.

## Verification

- Full pytest suite, Ruff, JavaScript syntax, strict MkDocs and Git whitespace
  gates completed successfully.
- Isolated Lab fixture, own cache/STEP mirror/runtime/logs, no Inventor session:
  installed Brave through bundled Playwright at 1916×1000 and 1400×700.
  Verified brief overview, reader/Edit/Read/close flow, sourcing/board/new links,
  back/forward/reload, missing note, all top tabs and no browser errors.
- Inspected both screenshots. Source diff confirms the modal markup is unchanged.
- Owner service verified idle and restarted via Lab, preserving LAN reach;
  scratch service stopped after checks. Human assembly modification excluded.

## Next steps

Judge overview length in real folders; the first authored paragraph already
serves as the summary used by folder cards in the parent catalog.

Provider usage: unavailable. Child-agent count: 0.
