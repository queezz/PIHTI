# Student local viewer and dependency requests — 2026-10-08

## Goal and decisions

Owner chose each student's own Windows checkout/Inventor installation and GitHub
issues/PR checklists for corrective submissions. Build that workflow without
operating the owner viewer, notifying contributors or changing native CAD.

## Changed

- Setup-PIHTI-Viewer.cmd and scripts/setup_viewer.py: one-time dependency setup or
  refresh in the declared external .venvs/pihti-dedup environment; explicitly chosen
  installed Python 3.12+ when missing. Never guess another project environment,
  create a venv in the checkout, replace a broken existing environment or change
  Windows execution policy.
- Start-PIHTI-Viewer.cmd: local-only viewer and browser launch with the checkout
  passed explicitly; no Lab dependency on student machines.
- Check-PIHTI-Submission.cmd and submission-report CLI/module: native read-only
  IAM/IDW/IPN direct-dependency reports for a chosen submission folder. Missing and
  external dependencies are named with relative referring documents and possible
  workspace matches. Machine paths omitted. Owner-open files, inspection failures
  and incomplete inventory make the report incomplete rather than certified.
  No CAD save/repoint/rename and no global silent-operation setting change.
- GitHub missing-dependency issue and PR templates: exact request, delivery by
  corrective PR/Pack-and-Go ZIP, recheck and receiving-workspace verification.
- Published student onboarding and README links, intake workflow and concrete
  request draft in requests/2026-10-08-boron-probe-missing-dependencies.md.
- Tool version pair/changelog 0.32.0. Existing lab pihti launcher remains valid.

## Verification

518 full-suite tests passed in 44.96s, declared pihti-dedup interpreter, fresh
external basetemp and no cacheprovider. Ruff passed including scripts/setup_viewer.py.
Setup script AST syntax passed. Strict MkDocs build passed into external TEMP.
Existing how-to-pr nav informational notice and upstream Material warning unchanged.

Real native report under PIHTI.ipj/Inventor 2027.1 found four expected vendor
dependencies in BoronProbe_2026/parts and correctly marked the report incomplete
because B_shield_5.iam remains loaded from the older audit. A separate ICF70TE
assembly report is clean. Portable MD/JSON retained in external TEMP. Tests cover
drawing references, stale-byte-string exclusion, external-path redaction, project
and scope refusal, owner document preservation, no-Inventor refusal and CLI output.

The student bootstrap was not run against the owner's installed environment:
no fresh-machine package installation or real batch/browser launch was performed.
Existing CLI serve tests cover browser/host/port dispatch; wrappers name that
verified command and explicit environment. The setup failure path retains the
console and original environment. Student fresh-machine validation remains useful.

## Notification and next steps

The issue draft is ready, but has not been posted/assigned and no message sent.
GitHub templates take effect remotely after the owner pushes the local commits.
Keep the request separate from subsequent archive UFC-152 consolidation failures.
Close it only after a corrected dependency package is checked in the receiving
checkout. The native report is presence evidence, not a geometry/revision approval.

Remaining source modification: bellows-probe/PIHT-Bellows-probe.iam was already
dirty when this task started and is not staged. No push, tag or owner-service
restart. Reports/build/test scratch retained outside Dropbox.

Usage: OpenAI / GPT-6; direct implementation, zero child agents; usage unavailable.
