# Rendered Markdown view for notes — pihti-dedup 0.5.0

**Date:** 2026-08-06
**Agent:** opus
**Goal:** stop showing Markdown files as raw text. A folder note *is* the
folder's `README.md` and a sidecar's prose is Markdown under YAML frontmatter;
MkDocs and GitHub already render both, and the viewer was the only surface
showing the source.

## Decisions

- **One renderer module, not a filter in `web.py`.**
  `src/pihti_dedup/markdown_view.py` owns the engine, the safety narrowing, and
  the plain-text reduction. `foldernote.note_excerpt` reuses it rather than
  re-implementing a markdown stripper, which is the same reuse rule
  `_note_display_text` followed for `strip_autogen_marker` in 0.4.1.

- **`tables` + `fenced_code` + `sane_lists`, and nothing else.** These are the
  three the MkDocs site relies on, so a table written for `docs/` looks the same
  in the viewer. Adding more would let the viewer render something the published
  site cannot.

- **Raw HTML is escaped, not executed.** This renderer runs over files that
  arrive through student pull requests, into a page that carries the viewer's
  own `FORM_TOKEN` next to localhost endpoints that rename, quarantine, and
  delete. A `<script>` in a submitted `README.md` would have been an XSS with a
  CSRF token sitting in the same DOM. `python-markdown` has no sanitizer since
  3.0, and pulling in `bleach` for this is disproportionate, so the two
  raw-HTML entry points are deregistered instead: the `html_block` preprocessor
  and the inline `html` pattern. The serializer then escapes the angle brackets,
  and blockquotes, tables, fences, and `&amp;` entities all keep working —
  deregistering the `entity` pattern was deliberately *not* done.

- **Comments are removed before rendering, not escaped.** With raw HTML gone,
  `<!-- ... -->` would otherwise render as visible escaped text. That would have
  been a visible regression: 0.4.0 deliberately preserves a comment the author
  typed further down a note (`test_an_authored_comment_further_down_is_left_
  alone`), and it must stay invisible when displayed. A comment is stripped
  before rendering, so it cannot smuggle markup either — it is deleted, not
  parsed.

- **Link schemes are filtered.** A treeprocessor drops `href`/`src` whose scheme
  is not http, https, mailto, or empty (relative and fragment targets), keeping
  the link text. `is_safe_url` removes whitespace and non-printables first,
  because a browser ignores them inside a scheme and `java\nscript:` must not
  read as safe.

- **The toggle is `<details>`, not JavaScript.** The catalog's folder-note
  editor was already a `<details>`; reusing the pattern means the editor works
  with scripting off, needs no state in `dedup.js`, and opens automatically when
  a save failed (`{% if error or draft is not none %}open{% endif %}`) so the
  rejected draft is never hidden behind a click.

- **The catalog does not render a generated index.** The work order said not to
  make the ~920 KB catalog worse. Rendering every folder note added 49,643
  bytes, almost all of it generated indexes — which are the folder's file list,
  duplicated three lines above the thumbnail grid that shows the same files.
  Rendering only *authored* notes there costs 15,602 bytes, nearly all of it the
  99 fixed edit-toggle wrappers. Measured against HEAD on the real workspace:
  939,953 → 955,555 bytes (+1.7%), render time unchanged at ~0.7 s. The folder
  page renders a generated index in full; only the catalog abstains.

- **Excerpts are plain text, not markup.** `note_excerpt` now reduces the line
  before truncating, so the 150-character budget is spent on prose and the cut
  can never land inside a `**` pair and leave the marker showing.

## Changed

- `src/pihti_dedup/markdown_view.py` — new. `render()`, `plain_text()`,
  `is_safe_url()`, and the `_SafeLinks` treeprocessor. The configured
  `Markdown` instance is thread-local and `reset()` per call, because a
  `Markdown` object carries per-document state and Flask serves threaded.
- `src/pihti_dedup/foldernote.py` — `note_excerpt` reduces a line to plain text
  before truncating.
- `src/pihti_dedup/web.py` — `sidecar_html` in `_part_context`, `note_html` in
  `_folder_context` and `_catalog_folders` (authored notes only there).
- `templates/part.html`, `folder.html`, `catalog.html` — rendered view by
  default, raw textarea inside a `<details class="raw-editor">`.
- `static/dedup.css` — `.markdown-body` typography, `.raw-editor` /
  `.edit-toggle`; `.sidecar-prose` lost its `white-space: pre-wrap`, which was
  the whole point of the old raw view.
- `pyproject.toml` — new runtime dep `markdown>=3.6`; version 0.4.1 → 0.5.0,
  matched in `src/pihti_dedup/__init__.py`.
- `.agents/CHANGELOG.md`, `.agents/directions.md` (queue item pruned),
  `.agents/dedup-viewer-design.md` (new "Rendered Markdown view" section).
- `tests/test_markdown_view.py` — new, 7 tests. `tests/test_web.py` — 4 new.

## State

- `pytest -q` — **113 passed** (was 102; +11).
- `ruff check src tests scripts/find_duplicates.py` — clean.
- `git diff --check` — clean.
- Flask test client only; no live server was started.
- No `README.md` or sidecar in the workspace was written.

## Next

- The DWG/STL/STEP preview chunk is the remaining queued item; the contract is
  in `log/2026-08-05-mesh-preview-spike.md`.
- If the catalog ever does need the generated indexes rendered, the honest fix
  is the one `directions.md` already names — load the editor on demand instead
  of inlining 99 of them — not more inline HTML.
