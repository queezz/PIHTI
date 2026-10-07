---
name: Missing CAD dependencies
about: Request the exact files or reference corrections needed for a submitted CAD package
title: "Complete CAD dependencies for <submission>"
labels: ''
assignees: ''
---

## Submission

PR(s):
Submission commit:
Author/contributor:
Primary assembly and submission folder:

## Requested files or link corrections

Paste the checklist from `Check-PIHTI-Submission.cmd` or attach its report.
Include each exact filename and the referring assembly/drawing. Distinguish
unsubmitted files from later archive changes; do not attribute a static filename
warning to the contributor without native verification.

## Response

- [ ] Supply the native dependency files in a follow-up PR, or attach a Pack-and-Go ZIP.
- [ ] List existing shared components and required external libraries by relative path/name.
- [ ] If a file was renamed or superseded, explain the replacement and fix its referring documents in Inventor.
- [ ] Reopen saved assemblies and drawings with `PIHTI.ipj` active.
- [ ] Attach a new native submission report and reference the corrective PR here.

## Verification before closing

Reviewer: verify the corrected package in the receiving checkout, check filename
collisions and intended revisions, then close this issue after the corrected
references resolve. A thumbnail or cached drawing is not sufficient evidence.
