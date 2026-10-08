# Folder sourcing brainstorm boards

## Goal

Capture many supplier links and images during a design browsing spree, without
requiring a detailed sourcing option for every possibility. The owner selected
a freeform folder board first.

## Decisions and changed paths

- Add a Brainstorm board door to the persistent sourcing option rail. Detailed
  options remain available beside it; a board-only folder opens its board.
- Store ordinary Markdown at `sourcing/_brainstorm.md`, excluding that reserved
  filename from option parsing and notes-check sourcing findings. Share the
  existing guarded attachment route and relative Markdown image links.
- Provide an optional item-name/link helper, Enter to insert, automatic bare-URL
  formatting on batch paste, and image paste/drop in both Write and Read.
  Saved boards open in Read to keep the screen easy to scan. Ctrl+S saves.
- Preserve drafts on revision conflicts, guard editing with the existing local
  token rules, protect unsaved navigation, and refuse Save while images upload.
- Change sourcing routes/parser, shared navigation, board template, CSS/JS,
  sourcing regression tests and README; bump tool version to 0.34.0 and record
  the shipped milestone. No CAD or real sourcing content was edited.

## Verification

- Full pytest suite: 522 passed. Regression coverage includes ordinary Markdown
  round trips, localhost/token guards, stale revision protection, invalid folders,
  board-only discovery and local attachment rendering with sanitized HTML.
- Ruff, JavaScript syntax, strict MkDocs build and Git whitespace checks pass.
- Installed Brave through bundled Playwright against an isolated Lab fixture:
  named link including brackets and URL parentheses, batch paste preserving
  existing Markdown, image drop, Ctrl+S, reload, gallery, option/board navigation,
  unsaved warning, all eight tabs with back/forward/reload, 1916×1000 and 1400×700.
  Inspected screenshots; no browser errors or horizontal overflow.
- Fixture has its own workspace/cache/STEP mirror/runtime/logs, no live Inventor
  session. Owner service verified idle before applying the update through Lab;
  LAN reach preserved. Fixture service stopped after checks.

## Next steps

Use the board during a real browsing spree and judge whether Markdown capture
needs an additional per-item visual composer. Current individual options remain
the place to refine prices, status and CAD associations.

Provider usage: unavailable. Child-agent count: 0.
