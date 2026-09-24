# Hero files and main assemblies (pihti-dedup 0.17.0)

**Goal:** queezz, 2026-09-24: "I want to be able to designate hero file and
assembly. Or a few. Now is good, but dedicated main assemblies is best."
Plus two amendments from the same session: drop the "N recoverable files"
shout from the top bar, and make the folder note readable on the rail with a
reader-first modal.

## Decisions

- A hero is `hero: true` in the file's metadata sidecar. The sidecar is the
  one per-file metadata surface the owner has accepted: portable, beside the
  CAD file, Git-tracked by his own commit. Several heroes per folder are fine.
- The toggle writes one line into an existing sidecar and preserves every
  other byte (flow lists, CRLF, comments); with no sidecar it seeds one from
  iProperties exactly as "Create metadata" does, plus the flag.
- Heroes show as a "Main assemblies" row of double-width tiles first in the
  centre column on the root page and on folder pages, first in folder strips,
  with a gold edge mark and a legend entry, and as the inspector's first fact.
- The hero lookup is memoised per inventory snapshot plus a validation serial,
  so a sidecar edited outside the viewer shows up on the next refresh at a
  cost of about 14 ms of stats per snapshot.
- Top bar: the recoverable-files indicator and its per-page manifest read are
  gone; the Removed page's rail is the only place for that count.
- Folder note on the rail: the authored part rendered in a fixed budget
  (`clamp(5rem, calc(100vh - 42rem), 11rem)`), same on every folder at a given
  window height, so the inspector's top never moves (measured identical across
  long, short, generated, and missing notes). The modal opens as a reader;
  Edit swaps in the editor.
- Implementation by an Opus agent; design, review, gates, and commit here.

## Changed

- `src/pihti_dedup/sidecar.py` (hero key, one-line set/clear),
  `foldernote.py` (authored-part split), `web.py` (hero memo, toggle route,
  note rail context, top bar), templates `_file_tile`, `catalog`, `part`,
  `base`; `dedup.css`, `dedup.js`; tests `test_sidecar.py`, `test_web.py`.
- Docs and version 0.17.0: `README.md`, `.agents/CHANGELOG.md`,
  `.agents/dedup-viewer-design.md`, `pyproject.toml`, `__init__.py`.

## Verification

- pytest 269 passed (250 + 19 new), fresh basetemp; ruff clean;
  `node --check` clean; `git diff --check` clean; strict MkDocs build clean.
- Perimeter Walk on a scratch copy (port 48971, stopped and port-checked):
  rails at 84px at every scroll position on root, folder, and part pages;
  tree rail at the same x on every page including Removed; inspector top at
  439px across five folders with different notes; toggle lands on its tile,
  Back/Forward/reload do not repeat the toast; all rendered links 200.
- Nothing written into the real workspace; the owner's 4185 kept its PID.

## Loose ends

- Clearing a hero from the root page removes its tile from the row, so only
  the toast confirms the action.
- The Hero button acts on whatever the inspector shows; the name sits right
  above it and the toast names the file.

## Next

- Set the two heroes the owner named today: `Plasma Vessel/Plasma-Flange-2024/
  cathode-box-on-a-flange.iam` and `Plasma Vessel/Cathode-Anode-Flange/
  Cathode-Anode-70IC-flange-with-feeds.iam`.
- `pihti-dedup notes check .` gate for `.agents/visual-pass.md`.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1 (Opus
  implementation); observed 2026-09-24 JST.
