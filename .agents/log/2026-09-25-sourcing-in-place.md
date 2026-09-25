# Sourcing in place — pihti-dedup 0.28.0

## Goal

The owner, on the bellows folder with two options for one small assembly:
"Going to sourcing and back is awkward, I get lost. And I already have two
links for one small assembly. It'll grow." Show sourcing where he already is,
and make it ready for many options.

## Decisions

- The folder's options are tiles in the catalog folder page's main column,
  under the files and inside the same `data-thumb-grid`, so hover, the arrow
  walk, and the inspector work on them unchanged. One section per folder,
  one line when empty; the root and a search have none.
- The picture is the first image the note links from its own
  `attachments/` (`sourcing.first_picture`); PDFs and missing files are
  passed over; no picture gives a `data:` placeholder.
- The inspector builds an option's facts from data attributes
  (`data-inspect="sourcing"`, vendor, part number, price, status, url, date,
  `data-for` as JSON), since a link cannot sit inside the tile's link. The
  hero and cover forms are hidden and disarmed for an option; an Edit option
  chip takes the foot row.
- Order: `STATUS_ORDER` received, ordered, quoted, candidate, rejected, newest
  first within each. Rejected tiles fold into one closed `<details>` "N
  rejected"; the arrow walk skips a closed fold and `#option-<slug>` opens it.
- A `for` name means the file in the note's own folder, or, when that folder
  has none, every catalog file carrying the name. The part page lists all of
  them; the folder section lists only the folder's own notes.
- The rail line keeps its 1.25rem: count as an in-page `#sourcing` link plus
  Add option. The part page's `sourced` signal stays, now "N sourcing
  options", with the rows below it.
- The editor takes `back=<file>` (validated as a workspace file); Save goes
  there with `?option=<slug>` for the toast, else to the catalog tile; Cancel
  and the rail button follow. `/sourcing/<folder>` is a 302 to
  `/catalog/<folder>#sourcing` (`?saved=` lands on the tile). `/sourcing`
  stays as the archive-wide list with its Status filter; new, edit, attach,
  and the attachment route are unchanged.

## Changed paths

- `src/pihti_dedup/sourcing.py` (`STATUS_ORDER`, `by_status`, `first_picture`)
- `src/pihti_dedup/web.py` (`_sourcing_index` files and named, `_option_tile`,
  `_for_links`, `_option_toast`, `_sourcing_back`, catalog and part contexts,
  redirect, editor `back` and `for`)
- `src/pihti_dedup/templates/_file_tile.html` (`option_tile`),
  `catalog.html`, `part.html`, `sourcing.html` (folder mode removed),
  `sourcing_edit.html`
- `src/pihti_dedup/static/dedup.js` (inspector option facts, fold-aware walk,
  `#option-` landing, file count), `dedup.css`
- `tests/test_sourcing.py`, `tests/test_web.py`
- `pyproject.toml`, `src/pihti_dedup/__init__.py` (0.28.0), `README.md`,
  `.agents/dedup-viewer-design.md`, `.agents/CHANGELOG.md`

## Verification

- Five new tests: the folder section, the inspector data attributes, the sort
  and rejected fold, the part-page rows with Add and back, the redirect.
  Existing sourcing and web tests updated for the new links.
- Gates: pytest, ruff, `node --check`, `git diff --check`, `notes check`,
  mkdocs strict build.
- Browser, scratch server on 127.0.0.1:4197 (scratch cache root and STEP
  mirror, `--refresh-seconds 0`, killed afterwards, port free; the live
  viewer on 4185 was not touched), at 1600x1000 on the real `bellows`
  folder: two candidate tiles with their screenshots under the files; hover
  and ArrowDown from the last file tile show an option in the inspector
  (price, status, the Amazon link, `bellows.iam`, date, Edit option); the
  rail line keeps 20px with the chip inside; `/sourcing/bellows` lands on
  `#sourcing`; `#option-probe-rails` focuses and shows that tile; the
  `bellows.iam` page lists both rows and Add option; the new form comes
  pre-checked with Cancel back to the part page. No console errors. Nothing
  was saved through the scratch server.

## Next steps

- No rejected option exists yet; the fold was checked in tests only.
- Deleting an option or an attachment is still not built.
