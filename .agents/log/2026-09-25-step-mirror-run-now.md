# Export fresh STEPs from the mirror page (pihti-dedup 0.26.0)

**Goal:** queezz, 2026-09-25: "A button to run conversion? Ask the user
(mostly me) to start Inventor, and push the button for fresh STEPs". The
background job exports one file a minute; `step-mirror sync` is the fast fill
but lives on the command line. The STEP mirror page now offers the same batch.

## Decisions

- `MirrorBatch` in `step_mirror.py`, one per app
  (`app.extensions["pihti_step_mirror_batch"]`), on its own daemon thread,
  never inside a request and never on the snapshot ticker. It follows `sync`:
  waits up to 30 s for a background tick already exporting
  (`MirrorJob.wait_idle`), closes leftovers, takes the mirror's own queue
  (oldest source first, not `sync`'s folder-by-folder order), logs and passes
  over files open in Inventor, reads the pre-check's reference context once and
  hands it to every export (so needs-Doctor assemblies never reach Inventor and
  the where-used index is not rebuilt per file), and runs `StepMirror.sync`
  with the 60 s per-file timeout and its probe-and-continue rule;
  `NOT_ANSWERING` ends it with that reason.
- Stop: `export_many` gained `should_stop`, asked before each file, ending
  with `STOP_REQUESTED` ("stopped on request"); the export in progress is
  never interrupted. `StepMirror.sync` gained `on_start`, `should_stop`, and
  `context` (passed to `export` only when given, so callers that wrap
  `export` keep working).
- `MirrorJob` gained `yield_to`; the viewer wires it to `batch.active()`.
  Export-now on a file answers "STEP not exported: the batch export is
  running" while a batch runs instead of timing out on the shared session.
- Routes: `POST /step-mirror/export` and `POST /step-mirror/stop` (form
  token, loopback, redirect back to `#mirror-batch`), `GET
  /step-mirror/status` (JSON: state, running, total, done, exported,
  not_exported, needs_doctor, open_in_inventor, current, reason, last, line,
  counts). No session: redirect with the notice "Inventor is not running;
  nothing started.", never a 500. A second start: notice "A batch is already
  running." Stop needs no notice; the status line says "Stopping after this
  file".
- Page: everything lives in the Inventor rail card: the notice, the status
  line, "Not exported: <file>: <outcome>" for the last failure, the **Export
  fresh STEPs** chip with "N waiting" (N excludes needs-Doctor), or
  "Nothing to export.", or "Start Inventor, open PIHTI.ipj, then come back"
  without a session, and the **Stop after this file** chip while running.
  Notices are rail notes, not floating toasts. The script polls every 3 s
  only while the batch runs (stops after three failed polls), updates the
  line and the Mirror card counts in place, and hides the pre-batch "N
  waiting"; the lists refresh on the next load.
- Never launched from the web, never `SilentOperation`.

## Changed paths

- `src/pihti_dedup/inventor_session.py` — `STOP_REQUESTED`, `should_stop`.
- `src/pihti_dedup/step_mirror.py` — `MirrorBatch`, `MirrorJob.yield_to` and
  `wait_idle`, `export(context=)`, `sync(on_start=, should_stop=, context=)`.
- `src/pihti_dedup/web.py` — batch wiring, three routes, `BATCH_NOTICES`,
  export-now "busy".
- `src/pihti_dedup/templates/step_mirror.html`, `static/dedup.js`,
  `static/dedup.css` — the card, the poller, five small rules.
- `tests/test_step_mirror.py` — 11 tests: stop between files in
  `export_many`, a full batch with an open file, leftovers and needs-Doctor,
  second start, stop, not answering, job yields, no session on the page,
  start and status JSON shape, second start / stop / export-now notices,
  the viewer's job yielding to the page batch.
- `pyproject.toml`, `src/pihti_dedup/__init__.py` — 0.26.0.
- `README.md`, `.agents/dedup-viewer-design.md`, `.agents/CHANGELOG.md`.

## Verification

- pytest 454 passed, fresh basetemp; ruff clean; `node --check` clean;
  `git diff --check` clean; strict MkDocs build clean.
- Scratch viewer on 127.0.0.1:48993 with a fake Inventor (2 s per export,
  12 parts, scratch cache and mirror): the button started the batch, the line
  moved "Exporting 1 of 12 · part00.ipt" to "Exporting 5 of 12", Missing
  counted down in place, Stop gave "Stopping after this file · 7 of 12 done"
  then "Stopped · exported 8 of 12" with the button back; without a session
  the card showed the "Start Inventor…" line. Server killed, port free.
- Not verified without a real Inventor: the batch through a live session, a
  real dialog timeout mid-batch, and the job handing over to the batch while
  the owner designs.

## Next steps

- With the owner present: open Inventor and `PIHTI.ipj`, restart `lab
  pihti`, press Export fresh STEPs with a few files stale, watch the line,
  press Stop once, confirm the export.log lines and that nothing the owner has
  open was touched.

## Usage

- Provider: Anthropic; implementation agent: Claude Opus 5.5; observed
  2026-09-25 JST.
