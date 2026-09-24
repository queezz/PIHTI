# Hero polish, featured files, and ranked folder strips (pihti-dedup 0.19.0)

**Goal:** queezz's live feedback on 0.17.0/0.18.1, 2026-09-24: hero cards
too big on the landing page; "Clear hero" in the inspector was a bad place
(he cleared one by accident); hero cards did not lead into their folder; the
gold left-edge bar "reads as if the item is being edited... that's from
lecturedeck, this is a two-rail webui"; "I still want an ability to bring up
what is important in the folder to the folder thumbs card"; and ContentCenter's
card should show the kinds of parts inside before entering.

## Decisions

- Hero tiles are ordinary tile size. The folder path under a hero is a link
  and each tile carries **Open folder**; preview and name still open the part.
- No coloured edge bars on catalog tiles at all: every signal is a dot in the
  tile corner (duplicate kinds, generic name as a ring, newer-same-name, hero
  gold, featured muted), same dots in the legend. Lecturedeck is a
  presentation deck, never a webui model (fleet RULES.md §10). Edge accents
  remain on Duplicates, Renames and Doctor cards, which are not tiles.
- The inspector carries no buttons; it states "Main assembly" and "Featured"
  as facts. Both toggles live on the part page; clearing asks first.
- `featured: true` is a second sidecar flag: leads the strip of every folder
  card above the file, without joining the Main assemblies row.
- Folder strips are manual-first: heroes, then featured, then a ranked
  round-robin across immediate subfolders and the folder's own files: an
  assembly nothing references, then any assembly, then a part, then drawings
  and exports; largest first, path order on ties. So ContentCenter's card
  shows one thing per drawer and an assembly holder contributes its assembly.
- The accidentally cleared hero on `cathode-box-on-a-flange.iam` was restored
  from the committed sidecar before the change.
- Implementation by an Opus agent; README correction, review, gates, and
  commit here.

## Changed

- `src/pihti_dedup/sidecar.py` (`featured`, `with_flag`/`set_flag`),
  `web.py` (dots, flags in one pass, `/part/<path>/featured`, strip memo with
  ranked round-robin), templates `_file_tile`, `catalog`, `part`; `dedup.css`,
  `dedup.js`; tests `test_web.py`, `test_sidecar.py`.
- Docs and version 0.19.0: `README.md` (hero paragraph rewritten to the
  current behaviour), `.agents/CHANGELOG.md`, `.agents/dedup-viewer-design.md`,
  `pyproject.toml`, `__init__.py`.

## Verification

- pytest 281 passed, fresh basetemp; ruff clean; `node --check` clean;
  `git diff --check` clean; strict MkDocs build clean; `notes check .` clean.
- Perimeter Walk on a scratch copy (port 48977, stopped and port-checked):
  rails at the same x/top at every scroll position on root, folder,
  ContentCenter and part pages; hero and file tiles the same width and
  preview size; no card rule sets a coloured edge; folder links land and
  prefetch; clearing asks and cancel keeps the flag; 126 links return 200.

## Loose ends

- File tiles with a sidecar story still span two columns.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1 (Opus
  implementation); observed 2026-09-24 JST.
