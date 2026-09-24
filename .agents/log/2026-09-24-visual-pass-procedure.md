# Visual-pass procedure and the notes gate (pihti-dedup 0.18.0)

**Goal:** queezz, 2026-09-24: in a session he shows a screen, says what the
folder or assembly is and how it is serviced, "the agent would add that into
the folder/assembly notes and the site would pick it up and show it back to
me... Do you think we need to build some CLI or agentic rules for that? Then
make them."

## Decisions

- No new storage. Folder notes (`README.md`) and file sidecars
  (`<cad filename>.md`) already are the surfaces the viewer, MkDocs, and
  GitHub show. What was missing was the procedure and a gate.
- `.agents/visual-pass.md` is the procedure: where each kind of statement
  lands, the note shape (title, one summary sentence, short sections,
  generated inventory kept below, marker removed), and the rules: only the
  owner's words become facts, authored text is never overwritten, CAD files
  are never touched, paths stay portable, notes are committed separately.
- `pihti-dedup notes check .` is the gate: marker drift on an authored note,
  an authored note without a summary sentence, a sidecar that does not parse.
  Read-only, exit 1 on findings. The generated-notice exemption covers both
  generator variants (`> Generated CAD inventory` and ContentCenter's
  `> Auto-generated index`).
- Two notes were written from his narration in the same session and
  committed separately (`95dfd1f`), and the two main assemblies were marked
  hero with one sentence each (`f7874f4`).
- The gate was implemented by a Sonnet agent; the procedure, the notes, the
  sidecars, review, and commits here.

## Changed

- `.agents/visual-pass.md` (new), `AGENTS.md` and `.agents/README.md`
  pointers.
- `src/pihti_dedup/notes_check.py` (new), `src/pihti_dedup/cli.py`
  (`notes check`), `tests/test_cli.py` (5 tests).
- Version 0.18.0: `pyproject.toml`, `src/pihti_dedup/__init__.py`,
  `.agents/CHANGELOG.md`.

## Verification

- `notes check .` on the real workspace: clean, exit 0.
- pytest 274 passed, fresh basetemp; ruff clean; `git diff --check` clean.

## Next

- Run a visual pass on the remaining Plasma Vessel subfolders and on the
  probes; each pass is one content commit.
- The procedure's session shape assumes the running viewer; if a pass ever
  needs a fresh instance, it is queezz's `lab pihti`, never a scratch start
  on his port.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1
  (Sonnet implementation); observed 2026-09-24 JST.
