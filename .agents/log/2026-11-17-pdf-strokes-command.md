# Add the PDF line-thinning command

- Goal: make the shop-PDF stroke thinning repeatable. Until now it had been
  done twice by hand-written scripts that were never committed.
- Added `src/pihti_dedup/pdf_strokes.py` and the `pihti-dedup pdf-strokes
  SOURCE TARGET --pages 5-17` subcommand. It needs no workspace and is handled
  before the workspace check.
- Decisions:
  - Standard library only, so no new dependency. Handles classic
    cross-reference tables with Flate-compressed or uncompressed content
    streams.
  - Refuses, writing nothing: incremental, encrypted or cross-reference-stream
    PDFs, indirect stream lengths, other filters, image pages, content streams
    shared across the page boundary, widths outside the mapping, width
    operators not at a line start, and overwriting the source.
  - The default mapping is the one verified on 2026-11-16.
- Bumped `pihti-dedup` to 0.37.0 in `pyproject.toml` and `__init__.py`.
  Updated the README, how-tos and CHANGELOG.

## Verification

- 12 new tests on synthetic Inventor-shaped PDFs, covering the selected-pages
  rewrite, the refusals, page ranges, uncompressed streams and the CLI.
- On the real bellows export (scratch `export-raw.pdf`), `--pages 5-17`
  produced a file byte-identical to the installed
  `bellows-probe/Bellows-Monotaro-A4-JIS.pdf`. `--pages 1-17` refused page 2,
  which carries the colour isometric image.
- Gates: see the commit (`ruff`, the full pytest run, `git diff --check`).

## Next

- Nothing open for this command. The cover pages and the open owner decisions
  are listed in the [annotation pass log](2026-11-16-bellows-drawing-annotation-pass.md).
