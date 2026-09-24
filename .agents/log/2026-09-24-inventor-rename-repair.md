# 2026-09-24 — Rename with repair through Inventor (pihti-dedup 0.21.0)

## Goal

Rename a CAD file and repoint the referring assemblies through the running
Inventor session, so Design Assistant is no longer needed. Built and tested
against a fake session only; the single real run is done separately with the
owner present.

## Decisions

- `inventor_session.py` encodes the proven order: open every referrer
  invisibly, rename on disk, `ReplaceReference` on descriptors matched by
  basename, `Save2(False)`, `Close(True)`, reopen to verify. `connect()` is the
  only function that reaches a real Inventor.
- Every call sequence runs on its own worker thread and COM apartment; the
  caller waits only while the worker makes progress (60 s, 5 s for probes).
  On timeout the worker is cancelled: nothing more is renamed or saved, and
  what it opened is closed when Inventor answers. A second call while one is
  stuck fails at once.
- A document already open in the owner's session is never opened, saved, or
  closed; the file itself being open refuses the rename.
- Added beyond the brief: in a collision (other files keep the old name), a
  descriptor that resolved to a surviving copy before the rename is not
  repointed, so an assembly using the other copy is not rewired. The web
  confirmation is built by `plan_repair` (open, read, close) so it names only
  the documents that will really be saved.
- The ledger gains `repaired` and `repair_note`; a fully repaired rename is
  settled with `will_prompt` false. `build_index(settled=...)` drops the fossil
  old name from repaired referrers.
- `create_app` resolves `inventor_session.connect` at call time;
  `tests/conftest.py` pins it to None for the whole suite.

## Changed paths

- `src/pihti_dedup/inventor_session.py` (new), `renames.py`, `whereused.py`,
  `web.py`, `cli.py`, `__init__.py`
- templates `_repair_confirm.html` (new), `doctor_name.html`,
  `doctor_assembly.html`, `part.html`, `renames.html`; `static/dedup.css`
- `tests/conftest.py`, `tests/inventor_fake.py`, `tests/test_inventor_session.py`,
  `tests/test_inventor_repair_flow.py` (new)
- `pyproject.toml`, `README.md`, `AGENTS.md`, `.agents/CHANGELOG.md`,
  `.agents/dedup-viewer-design.md`

## Verification

- pytest: 341 passed (309 existing unchanged); ruff clean; `node --check`
  clean; `git diff --check` clean.
- Perimeter Walk on a scratch server (synthetic workspace outside Dropbox,
  fake session, port 48971; stopped by tree kill, port verified free; the
  owner's 4185 listener untouched): every top tab from the Doctor name page,
  every link on Doctor name and Renames (all 200), Back/Forward, reload on the
  deep link, `#rename` anchor, the full rename-and-repair flow from both forms,
  the partial and full Renames states, the no-Inventor state, no horizontal
  overflow at 375/1920. Rail tops: Renames and part page 84px at every scroll
  depth at 700 and 1000px. Doctor name rail rests at 202px and pins at 84px
  when the page scrolls at 700px; that page's head section sits above its
  grid, unchanged by this work.
- Screenshots in the browser pane timed out; the walk used DOM measurements.

## Next steps

- The real run, with the owner present: `pihti-dedup rename <path> <new name>
  . --repair --dry`, then without `--dry`.
- Check in the real run that `FullFileName` reports the resolved path before the
  rename, which the collision-survivor guard relies on.
