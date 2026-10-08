# Compact folder-card content

## Goal

Remove repeated folder identity, redundant equal counts and wasted vertical
space identified by the owner in the folder card screenshot.

## Decisions and changed paths

- Show the folder name once as a heading, with Copy path alongside it. Keep
  the relative path as the heading tooltip and in the catalog breadcrumb.
- Replace Files here / Below here rows with one compact count. Show additional
  files in subfolders only when the subtree contains more than the direct count.
- Keep the readable overview and existing full-note button, separate sourcing
  card and inspector behavior. Shrinking metadata returns space to the inspector.
- The owner also identified the sourcing action card's mixed hierarchy and
  unclear Save option label. Put folder navigation above a separated save block,
  with its status directly underneath. Existing items use Save changes, new ones
  Create option; unchanged existing forms disable Save until edited. Move New
  option beside the option list heading. Board saves retain their own label.
- Change catalog and sourcing navigation templates, narrowly scoped CSS,
  dirty-state JavaScript, existing route assertion, README, version pair and
  changelog. Tool patch version 0.34.3. No CAD edits.
- The owner identified redundant Catalog / Sourcing context and the distant
  filter in the overview. Remove that header; consolidate Find and Status in
  one left-rail card and remove the duplicate scope/count summary card.

## Verification

- Full suite: 522 passed. Ruff, strict MkDocs and whitespace checks passed.
- Isolated Lab browser fixture at 1916×1000 and 1400×700: inspected screenshots,
  verified note view/edit/read/close, sourcing/board links, back/forward/reload,
  empty folder and top tabs. No browser errors or horizontal overflow.
- Updated the scratch browser's previous card-height assertion: its ratio to
  the folder card became obsolete when the folder itself shrank; the sourcing
  card remains at most 60px tall. Stopped the stalled owned test process and
  repeated the checks successfully.
- Additional browser verification at both sizes: adjacent save status, save
  enables on edits, disables when reverted or saved, edited supplier persists
  through save/reload, new uses Create option and board uses Save board.
  Inspected screenshots. Cleaned up the owned test browser after its shutdown
  stalled; all workflow checks had completed successfully.
- Overview filter: text/status compose, Enter stays in sourcing, Escape clears,
  no-match feedback and both viewport sizes verified. Sourcing route suite
  passed after the template move; full suite passed before it (522 tests).
- Verified idle owner viewer before applying through Lab, preserving LAN reach;
  stopped the isolated fixture. Human assembly modification excluded from commit.

## Next steps

Use the condensed folder identity and count line while browsing real designs.
Full note reading remains in the established modal.

Provider usage: unavailable. Child-agent count: 0.
