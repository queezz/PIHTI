# Catalog metadata prominence

Date: 2026-08-06

## Goal

Make Catalog cards explain hardware rather than asking previews and filenames
to carry the whole story, including at the workspace root.

## Decisions

- Sidecar prose is the strongest file narrative and takes precedence over an
  Inventor Description. Either produces a wide image-and-story card.
- Status, tags, useful material, and a Part Number that differs from the
  filename appear as chips. Facts without prose stay on a compact card; visual
  QA rejected double-width material-only cards because their narrative column
  was mostly empty.
- Inventor metadata is read only for the bounded records rendered on the current
  route and cached by path, modification time, and size. A changed CAD record is
  reread; switching away and back to an unchanged folder is not.
- Folder-note excerpts join wrapped summary paragraphs. Authored folder cards
  use a taller, multiline treatment, the current folder summary is part of the
  heading, and the Catalog root uses the opening summary from `README.md`.
- The owner's pending `Plasma Vessel/README.md` edit was used for live QA but
  remains unstaged and uncommitted by this tooling change.

## Changed paths

- `src/pihti_dedup/web.py` and `foldernote.py`
- `src/pihti_dedup/templates/catalog.html`, `folder.html`, and `_file_tile.html`
- `src/pihti_dedup/static/dedup.css`
- `tests/test_web.py` and `tests/test_foldernote.py`
- `README.md`, `.agents/CHANGELOG.md`, and `.agents/dedup-viewer-design.md`
- `pyproject.toml` and `src/pihti_dedup/__init__.py` (`pihti-dedup` 0.9.0)

No CAD document or user-authored metadata file was changed.

## Verification

- Focused web and folder-note suite: 74 passed.
- Browser QA used an isolated `pihti-qa` service on port 4198. The root purpose,
  multiline folder summaries, compact material chips, and wide Description
  cards were checked at desktop width. The scratch process was stopped and its
  port verified released.
- Full test gate: 182 passed.
- Ruff: `src`, `tests`, and `scripts/find_duplicates.py` clean.
- `mkdocs build --strict`: passed; only the existing unlisted `how-to-pr.md`
  informational notice appeared.
- `git diff --check`: clean.

## Next steps

Add concise prose to high-value part sidecars over time. The presentation is now
ready for it; no bulk metadata invention is warranted.
