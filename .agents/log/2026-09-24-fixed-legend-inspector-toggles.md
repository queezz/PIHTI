# Fixed legend and inspector toggles (pihti-dedup 0.19.1)

**Goal:** queezz, 2026-09-24: "I hate jumping nav/legends/rails. That legend
for signals is jumping. Why don't we make a single legend? Signals is not an
intuitive name. Also I have to open a file to make it featured or main
assembly. Why? We have the inspector." And: the earlier inspector button was
wrong because it "was on top and orange, crying to push it, and no
confirmation".

## Decisions

- One card, "Legend", anchored at the bottom of the left rail with a constant
  height and always the full set of marks; the folder card has one fixed
  height on root, folder and search pages; the inspector fills the space
  between. Measured inspector/legend tops: 440/804 px at 1920×1000 and
  344/504 px at 1920×700 on root, two folders, and search, at every scroll
  position; the part page has no inspector and its legend sits at the same
  top.
- The inspector carries both placement toggles at its foot, styled like
  "Copy path", never accent-coloured. Setting acts at once; clearing asks and
  names the file; the script refuses a submit whose form names a different
  file from the one shown.
- Implementation by an Opus agent; review, gates and commit here. The session
  was paused on the owner's request before the next amendment (badges).

## Changed

- `src/pihti_dedup/web.py`, templates `_file_tile`, `catalog`, `part`;
  `dedup.css`, `dedup.js`; `tests/test_web.py`; version 0.19.1 in
  `pyproject.toml`, `__init__.py`; `.agents/CHANGELOG.md`,
  `.agents/dedup-viewer-design.md`, `README.md` (two phrases).

## Verification

- pytest 285 passed, fresh basetemp; ruff clean; `node --check` clean;
  `git diff --check` clean. Perimeter Walk on a scratch copy (port 48991,
  stopped and port-checked): set, cancel-clear, clear, set from search, Back
  without repeated toast; 120 links 200; folds at 1150 wide.
- The owner's instance restarted itself at 17:22 and he has since written a
  dozen sidecars (`featured`/`hero`) through it; those untracked `.md` files
  are his and were left for his own commit.

## Next (owner amendment received, not started)

- Replace the corner dots with fleet-style word badges (`clash`, `copy`,
  `renamed`, `unhashed`, `generic`, `newer`, `main`, `featured`) in a row
  under the tile's size line, same badges in the inspector and the Legend;
  reuse fleet's chip CSS shape and tints (WEBUI.md names the vocabulary).
- README lines around 291–295 still describe coloured edges and "marks
  present on the page"; rewrite with the badge change.
- At 700 px tall the inspector keeps name, facts and toggles but drops the
  preview; the root page shows some empty space at 1000 px tall.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1 (Opus
  implementation, stopped at the owner's pause); observed 2026-09-24 JST.
