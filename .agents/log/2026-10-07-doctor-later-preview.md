# Doctor later row preview

## Goal and change
Deferred rows placed their entire path in the thumbnail grid column. Added the
same preview link and filename/folder pair as Ready rows; retained diagnosis and
Review now in their existing columns. Bumped the tool version to 0.31.3.
Changed template, version pair and changelog only, plus this handoff.

## Verification
81 focused mirror/version tests and 511 full-suite tests passed.
Ruff passed. Scratch browser at 1600x900 confirmed 72px preview column,
222px filename column, separate folder line, working part link and Back.
Screenshot retained; temporary viewport reset and tab closed. Scratch Lab process
tree launcher21564/listener37548 stopped and listener port 48943 cleared. Owner service untouched.
No real CAD, deferral records or unrelated dirty files changed.

## Next
Restart pihti through Helm for the corrected deferred row layout. No push/tag.
