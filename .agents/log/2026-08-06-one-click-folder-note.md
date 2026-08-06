# One-click folder notes

Date: 2026-08-06

## Goal

Remove the disclosure → note page → raw-editor interaction chain, give every
folder-note surface an obvious exit, and make short folder descriptions useful
in the Catalog without introducing a second metadata store.

## Decisions

- Use one native HTML `dialog` on each non-root Catalog folder route. Rendered
  Markdown and the token-protected raw editor stay together; native dialog
  semantics provide Escape dismissal in addition to explicit ×, **Close**, and
  backdrop controls.
- Redirect Catalog-origin saves to the same folder and reopen the dialog with
  success or validation feedback. Retain the full-page editor as an optional
  large-document surface.
- Make the full page navigable with breadcrumbs and rail action cards for the
  current folder, its parent, and Catalog home.
- Treat the first prose line below the note title as the short folder summary.
  This preserves `README.md` as the sole source while feeding the existing child
  folder card excerpt. Both editors explicitly request a one-sentence summary
  and seed that structure in their placeholders.
- Serve the exact `docs/assets/pihtiicon.svg` bytes used by MkDocs as the Flask
  favicon.

## Changed paths

- `src/pihti_dedup/templates/catalog.html`, `folder.html`, and `base.html`
- `src/pihti_dedup/static/dedup.css`, `dedup.js`, and `pihtiicon.svg`
- `src/pihti_dedup/web.py`
- `tests/test_web.py`
- `README.md`, `.agents/CHANGELOG.md`, and `.agents/dedup-viewer-design.md`
- `pyproject.toml` and `src/pihti_dedup/__init__.py` (`pihti-dedup` 0.8.0)

No CAD document, generated folder README, or metadata sidecar was changed.

## Verification

- Focused web and folder-note tests: 69 passed.
- Full test gate: 177 passed.
- Ruff: `src`, `tests`, and `scripts/find_duplicates.py` clean.
- `mkdocs build --strict`: passed; only the existing unlisted `how-to-pr.md`
  informational notice appeared.
- `git diff --check`: clean.
- Browser QA on an isolated `pihti-qa` scratch service confirmed the modal
  layout, one-click opening, two explicit close controls, backdrop dismissal,
  and automatic reopen after save. The scratch process and port were stopped
  and verified absent afterward.
- The served SVG favicon and MkDocs favicon have the same SHA-256:
  `5949036B776258A478D468BE43BEA2436DEFC30B11CB58A4CA88BC80ACF43769`.

## Next steps

None required for this interaction. Folder authors can progressively replace
generated inventory prose with intentional one-sentence summaries as they edit
notes; no bulk rewrite is warranted.
