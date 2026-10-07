# Cache coloured inspector geometry

## Goal
Diagnose slow Catalog / bellows navigation and repeated inspector work.

## Evidence and decisions
Owner catalog HTML measured 33-167 ms; colour loading bypassed the existing
persistent mesh cache, reread STEP bytes on every request, retained only two OCC
models, and forced no-store on metadata and binary routes. Bellows fine geometry
failed at the two-million-triangle cap after 83 seconds and repeated in 65 seconds.
Added machine-local appearance-meshes: source path/stat, schema and cap key;
atomic geometry and occurrence metadata; no OCC lock or STEP hash on cache hits.
Cache oversized refusals too. Map overrides stay live; JSON uses conditional ETags
and geometry is immutable under its digest URL. Real source changed during the
measurement, and its next request correctly refused the stale STEP mirror.
First build of changed geometry still costs time; no claim of eliminating that.

## Changed
simulation_web.py, viewer3d.js, response-cache exceptions in web.py; two cache
regression tests, README, version pair 0.31.1 and changelog.

## Verification
508 full-suite tests passed; final version/cache subset 8 passed. Ruff and JS
syntax passed; strict MkDocs and scoped diff check passed. Tests cover three-model
eviction, fresh-app restart, map-only edits, source change, conditional JSON,
immutable mesh and persistent cap refusal with cap invalidation.
Lab scratch browser verified part-page 3D, editor, Back/reload and colours with
no console errors. Cached synthetic model response ~2 ms. Screenshot retained.
Scratch launcher 8/listener 24740 stopped; earlier accidental default-port scratch
launcher 27928/listener 29512 was stopped before the corrected run. Ports 48943
and 5000 free; owner listener 4185 stayed 11108. All agent tabs closed. No CAD or
Inventor modifications; real cache-only reads/writes. Other dirty work unstaged.

## Next
Restart pihti through Helm to load 0.31.1. Large changed assemblies still build
once; future work could isolate cold tessellation from server CPU contention.
