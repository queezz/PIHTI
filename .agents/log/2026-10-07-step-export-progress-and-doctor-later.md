# STEP progress and Doctor later

## Goal and decisions
Keep STEP batch actions in place and let old reference blockers wait.
Added atomic portable .agents/doctor-later.json dispositions, expiring on source
size/mtime changes. Deferred assemblies leave automatic queues and active Doctor
reference complaints; actual missing coverage and blocker evidence remain.
Review now reverses the disposition. No real CAD or deferral records changed.

## Changed paths
New doctor_later module; step_mirror status; web routes/Doctor context; mirror
HTML/CSS/JS; mirror tests; README; version pair 0.31.0 and changelog.

## Verification
506 full-suite tests passed; final mirror suite 80 passed. Ruff, JS syntax,
strict MkDocs and scoped diff checks passed. Scratch Lab fake-Inventor browser
verified progressing batches, unchanged Start/Stop URL and scroll (688), reversible
deferral, Doctor deep link, Back/Forward/reload, all eight navigation views,
section anchors and Copy path. Rails stable at top/middle/bottom at 1600x1000
and 1600x700; no console errors. Screenshot retained in session visualizations.
Scratch port 48943: launcher 25636, listener 36720; stopped after testing.
Owner service port 4185 remained PID 11108. Temporary browser viewport reset.

## Next
Restart pihti through Lab/Helm to load 0.31.0, then defer individual blockers as
needed. Independent collisions stay visible. No push/tag; other CAD/ledger work
left unstaged.
