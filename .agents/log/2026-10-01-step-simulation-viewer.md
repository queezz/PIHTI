# STEP simulation viewer handoff — 2026-10-01

## Resume here

Target repository: PIHTI CAD (`cad/.`), C:\Users\queezz\Dropbox\Drawings\PIHTI. This chat was mistakenly attached to pihtivacuum. Owner requested stop and handoff; implementation is paused, uncommitted. Resume in the CAD project, inspect the scoped diff, then commit after the existing green gate. Do not redo implementation or rerun all checks unless changes justify it.

## Request and decisions

Fleet action letter `20260930-4d4ee4d1-c85bc8` from code/plasmatrace was received and collected after durable logging. Owner requested a dedicated STEP viewer for selecting, colouring and renaming parts for numerical simulation. No reply sent: incoming letter alone does not authorize outbound messaging.

Version 0.30.0 implements a STEP viewer tab, canvas/list picking, name/material/electrical-role/colour editing, role colour presets, search, fit, up-axis and isolate controls. Stable source plus authored occurrence names key the reusable JSON map. Unstable unnamed/duplicate occurrences cannot be saved. Real `simulation/parts.json` is deliberately empty; no real hardware assignments inferred.

Exports download a ZIP with AP242 prepared STEP, metadata/report and reusable mapping. World placements are baked into independent named products in mm. Original Inventor documents and mirror are preserved. Simulation export requires material and electrical role for every part; unmatched and absent mappings are reported. Standalone CLI refuses an existing destination. Source digest and map revision reject stale edits/exports. Mutations require loopback plus token. Optional dependency cadquery-ocp 8.0.1 is installed in the external pihti-dedup environment and declared in the simulation extra.

## Owned paths to review/stage

src/pihti_dedup/simulation_step.py
src/pihti_dedup/simulation_web.py
src/pihti_dedup/templates/simulation.html
src/pihti_dedup/static/simulation.js
src/pihti_dedup/static/viewer3d.js
src/pihti_dedup/web.py
src/pihti_dedup/templates/base.html
src/pihti_dedup/templates/part.html
src/pihti_dedup/static/dedup.css
src/pihti_dedup/__init__.py
pyproject.toml
AGENTS.md
README_SHORT.md
.agents/CHANGELOG.md
simulation/parts.json
tests/test_simulation_step.py
.agents/log/2026-10-01-step-simulation-viewer.md

Check actual status before staging: the repository contains many unrelated dirty hardware edits, rename-ledger changes and power-rack drafts. Never stage them. Baseline master HEAD was b764e07b56cd60f62da43f571fb62035b62088b3. No push, tag or commit made in this session. Use per-command safe.directory if needed; no global trust settings changed. Fleet requires local commit despite older local 'when asked to commit' prose. Suggested title: Add the simulation STEP viewer — v0.30.0; final trailer: agent: Codex.

## Verification complete

Final full suite: 502 passed in 56.15s, exit 0. Ruff src/tests/scripts/find_duplicates.py passed. Node syntax checks passed for both viewer JS files. git diff --check passed. Strict MkDocs build passed to external scratch. An intermediate asset-length failure caused by doubled Windows newlines was corrected; final full suite includes the fix.

Synthetic repeated translated boxes round-trip with unchanged world coordinates. Plasmatrace's own gmsh environment reads exact names Shapes/Kapton-0 and Shapes/Kapton-1 and exact colour (51,170,119,255), #33aa77. CLI successful export and repeat destination refusal checked.

Browser checked selection by canvas and list, metadata persistence, unsaved edit handling, incomplete simulation refusal, successful coloured and simulation bundles, isolate/fit/Y-Z-up/search/reload, surrounding tabs and part-page entrance, Back/Forward, rail geometry at 1400x1000 and 1400x700. No page scroll range; left rail scrolls internally. No new anchors. Latest Escape form reset was syntax/full-suite checked but not separately revisited in browser. No large owner simulation assembly has been annotated or validated; upcoming simplified assembly still needs the owner's map.

## Cleanup and remaining work

Synthetic Lab service step-test on port 48943 was stopped with lab_cli; PID 31924 process tree stopped and listener absent. Owner lab pihti service was untouched. Scratch evidence retained outside Dropbox at C:\Users\queezz\AppData\Local\Temp\pihti-step-viewer-20261001 (fixtures, exports, logs/config). Initial stop attempt used wrong module lab and failed harmlessly; corrected to lab_cli. No active scratch process remains.

Remaining: review scoped final diff, optionally revisit Escape UI reset, settle retained scratch marker conventions, then make the local commit. Start/restart owner lab pihti from an ordinary terminal to load backend and use STEP viewer. Do not send plasmatrace mail without human authorization. No subagents used; provider usage unavailable.
