# Dedicated catalog functionality and performance review

Requested by Kuzmin on 2026-11-19 after reviewing PLD in the catalog.

## First reproduction

At `/catalog/PLD`, native parts and assemblies display their embedded
thumbnails but reportedly fail to render interactive 3D despite existing STEP
copies. A direct `jis80-glass-115-retainer.stp` can be previewed. Compare it
with its `.ipt` and the matching `.iam`; also check `pld-octogon.iam`.
This is an owner report, not yet a diagnosed rendering cause.

Use the actual Still/3D controls in both the folder inspector and part page.
Inspect network responses and visible error states. Verify source-to-mirror
path mapping, case handling, freshness classification, mesh availability,
optional geometry dependencies, generation failures and cache keys. Read
`mesh_cache.py`, `geometry_preview.py`, `step_mirror.py`, `web.py` and the
inspector's JavaScript as needed. Test both native-to-mirror loading and
direct STEP loading, without requiring Inventor for an existing saved mirror.

## Broader review

- Exercise representative small parts, assemblies, and large meshes across
  multiple folders. Measure first-load and cached-load timings. Check whether
  expensive mesh work blocks catalog navigation or leaves a blank 3D view.
- Verify state transitions after source resaves, STEP refreshes, failed mesh
  attempts and service restarts. Errors should identify a useful next action
  and retries should recover without manual cache deletion.
- Inspect Doctor and STEP mirror together. Use the new required workflow in
  AGENTS.md and inventor-how-tos.md; distinguish native dependency errors,
  byte-scan evidence, naming advice and pre-existing deferred findings.
- Inspect background export timeouts and cleanup. On 2026-11-19, after
  restarting the catalog to load v0.37.1, the mirror page showed a timed-out
  `sliding-assembly-monotaro.iam`, one pending-close document and two stale
  bellows assemblies ready to export. Inspect current state rather than
  treating that snapshot as the live queue. Preserve owner documents,
  unsaved changes, renders and active commands.
- Inventory findings before changing CAD. Genuine missing student dependency
  packages and unresolved canonical-folder choices already have directions
  here; do not replace geometry or consolidate folders by appearance.

## Current baseline

- v0.37.1 fixes false missing-reference reports caused by raw scanning across
  non-contiguous OLE sectors. The full sleeve and end-washer names now resolve;
  live `/step-mirror` showed zero blocked references after the restart.
- The live `/doctor` snapshot still had 1 interrupted save, 2 missing names,
  14 ambiguous-name groups, 21 generic-name groups and 20 standard parts
  outside the library. These are archive-wide pre-existing findings, not
  evidence that every listed file needs renaming or deletion.
- Two assemblies remain under Doctor later. Their missing source packages
  are recorded in directions.md and were not substituted or hidden.
- Current tests: 543 pass. Ruff and whitespace checks pass. The active
  catalog service was restarted through `lab restart pihti`.
- Separate dirty owner artifacts include the bellows IDW/manual PDF/assembly
  PNG and a PLD print 3MF. Recheck Git status and preserve them.

## Completion criteria

Reproduce and fix the PLD 3D failure; prove the native-part and assembly views
work through their existing mirrors in both UI surfaces. Add regression tests
for diagnosed bugs, verify performance/recovery through real interactions,
and run the repository gates. Record remaining issues with reproducible
evidence. Update instructions where a repeatable review step was missing,
write a handoff and commit only the reviewed changes. No push.
