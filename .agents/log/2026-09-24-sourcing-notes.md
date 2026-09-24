# Sourcing notes with pictures (pihti-dedup 0.20.0)

**Goal:** queezz, 2026-09-24: "I need a place to store shopping options. Some
parts I source, and design around that. So I need to keep it nice and
discoverable." Not a table: "pictures, screenshots, maybe occasional pdf...
we have a good precedent already: pihti-log."

## Decisions

- One Markdown note per option in `<folder>/sourcing/<slug>.md` with
  frontmatter (`title`, `vendor`, `part_number`, `url`, `price`, `status` of
  candidate/quoted/ordered/received/rejected, `for` CAD filenames, `date`) and
  his prose; pictures and PDFs in `<folder>/sourcing/attachments/`, pasted or
  dropped into the editor the way pihti-log attaches pictures, embedded as
  standard Markdown (Obsidian `![[...]]` rewritten). Nothing is CAD, so the
  scanner and the tree ignore it; the notes travel with a folder rename.
- Read surfaces: a fixed-height Sourcing line in the folder card, a
  `/sourcing/<folder>` page of option cards with status badges and inline
  pictures, a `sourced` badge on the CAD tiles an option names plus a
  "Sourced" inspector row, and an archive-wide `/sourcing` page grouped by
  status, with a Sourcing tab in the top bar.
- Attachment boundary: writes need loopback plus the form token and a
  catalog folder; attach refuses over 25 MB and any bytes that do not match
  an allowed image/PDF extension, names files `YYYYmmdd-HHMMSS-<stem>.<ext>`
  with an exclusive open; `GET /sourcing-file/...` serves only a file that
  resolves inside the workspace, sits directly in `sourcing/attachments/`,
  and has an allowed extension, always `nosniff`; SVG carries a sandboxing
  CSP; PDFs inline; images versioned and immutable.
- The status filter hides non-matching cards. Fleet WEBUI says a rail
  control reorders rather than hides; the owner ruled live today that he
  wants fast filters (the catalog header filter hides too), so the owner's
  ruling stands here and is recorded as such.
- Legend gains a ninth badge and grows one row upward by the same amount on
  every page (tops 747 px at 1920×1000, 447 px at 1920×700; inspector top
  unchanged at 440/344). The Sourcing line costs the folder note about 26 px
  of its budget; at 700 px tall the note body is under one line. Desktop-only
  target, accepted.
- Deleting an option is not built (README says so). Implementation by an
  Opus agent; review, gates and commit here.

## Changed

- New: `src/pihti_dedup/sourcing.py`, templates `sourcing.html`,
  `sourcing_edit.html`, `tests/test_sourcing.py` (21 tests).
- `web.py`, `markdown_view.py` (relative-link resolve hook), `sidecar.py`
  (`split_frontmatter` shared), `notes_check.py` (sourcing finding), `cli.py`,
  templates `base.html`, `_folder_tree.html`, `catalog.html`, `part.html`;
  `dedup.css`, `dedup.js`; `tests/test_web.py`.
- Docs and version 0.20.0: `README.md` ("Sourcing notes"), `.agents/CHANGELOG.md`,
  `.agents/dedup-viewer-design.md`, `.agents/visual-pass.md` (Sourcing
  paragraph), `pyproject.toml`, `__init__.py`.

## Verification

- pytest 307 passed, fresh basetemp; ruff clean; `node --check` clean;
  `git diff --check` clean; strict MkDocs build clean; `notes check .` clean.
- Perimeter Walk on a scratch copy (port 48995, stopped and port-checked):
  114 links and images 200; paste and drop of PNG and PDF insert rendering
  embeds; a pasted `.exe` refused; save, edit, filters, Escape, Back/Forward
  behave; rail tops identical across root, folder, search, part and sourcing
  pages at every scroll depth.
- Left uncommitted on purpose: the owner's Inventor save of
  `bellows/bellows.iam` and his untracked sidecars.

## Next

- First real use: `bellows/sourcing/` for the bellows stage he is designing.
- Rename `bellows/` to a name of his choosing after the standard-parts mover
  has taken its two JIS bolts to ContentCenter (unique names first), then
  open the top assembly once in Inventor and save.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1 (Opus
  implementation); observed 2026-09-24 JST.
