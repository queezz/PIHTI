# One tile width, descriptions clamped (pihti-dedup 0.20.1)

**Goal:** queezz's screenshot, 2026-09-24 ("Well, good intentions..."): on
`ContentCenter/Aluminium-profiles` the tile with an Inventor description
rendered as the old two-column story card, and with subgrid rows the whole
row stretched to it, leaving tall empty tiles.

## Decisions

- Every file tile has one width and one column structure: preview, name, up
  to two clamped lines of description or sidecar excerpt (full text in the
  tooltip; Inventor descriptions also in the inspector), chips, size, badges.
  The story variant and its `span 2` are gone; `has_story` removed.
- Measured on a scratch copy at 1920 wide: rows on that page 251 px, every
  tile 150 px wide, size lines level; a folder without descriptions rows 166
  px; rails at 84 px at every scroll depth.
- Implementation by an Opus agent; review, gates and commit here.

## Changed

- `templates/_file_tile.html`, `static/dedup.css`, `web.py`,
  `tests/test_web.py` (3 updated, 1 added); version 0.20.1, CHANGELOG,
  design doc, README sentence.

## Verification

- pytest 308 passed, fresh basetemp; ruff clean; `node --check` clean;
  `git diff --check` clean; strict MkDocs build clean. Scratch port 48995
  stopped and free; owner's 4185 untouched.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1 (Opus
  implementation); observed 2026-09-24 JST.
