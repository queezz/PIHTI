# Isolate cold STEP tessellation

## Goal and decisions
Keep assemblies from holding up Catalog while preparing their display mesh.
The persistent cache solved repeats but cold OCC still ran in web request threads.
Added one worker process with one queued job, Windows below-normal priority,
120-second deadline, and process-tree shutdown for Windows venv launchers.
Live model routes return 202 immediately and clients poll; cached routes stay
immediate. The still image remains while preparing. Oversized coloured models
now report their refusal instead of starting a second plain-geometry build.
Tests/default synchronous apps retain their deterministic in-process path.

## Changed
New display_worker.py; simulation_web background dispatch; web registration;
viewer3d polling/abort and refusal handling; STEP editor shared polling; tests,
README, version pair 0.31.2 and changelog. No CAD or Inventor modifications.

## Verification
511 full-suite tests passed; final version/worker subset 11 passed. Ruff, both
JavaScript syntax checks, strict MkDocs and scoped staged diff check passed.
Regression tests hold a worker blocked while real Catalog completes, exercise
an actual child process to persistent geometry, and verify Windows tree kill.
Browser scratch: cold fixture becomes coloured 3D, opens editor with two parts,
Back/reload works, no console errors. Screenshot retained in visualizations.
A disposable copy of the real 6.15 MB bellows STEP returned 202 in 19 ms;
Catalog / Probes / Catalog after starting it took 87 / 4 / 6 ms.
Scratch Lab runs used 48943. Last launcher 41028/listener 40992 stopped; prior
launcher 34104/listener 27836 and worker launcher36516/interpreter32016 also
stopped. Port free and scratch processes gone. Owner service remained untouched;
its PID changed from 11108 to 41540 during the session by external action.
All agent browser tabs closed. No user metadata or real CAD files changed.

## Next
Restart pihti through Helm to load 0.31.2. Changed geometry still needs its first
build, but its CPU/GIL work is isolated from the web process. No push or tag.
