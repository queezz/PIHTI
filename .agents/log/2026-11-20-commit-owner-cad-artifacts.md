# Commit the remaining owner CAD artifacts

- Goal: Kuzmin explicitly requested committing the remaining assembly updates,
  PDF, image and 3MF after the clamp changes were committed.
- Included the saved `bellows-probe/flange-clamp-114.iam` and
  `bellows-probe/monotaro-rear-driven-carriage.iam` updates.
- Added the owner's `bellows-probe/Bellows-Monotaro-A4-JIS-man.pdf`,
  `bellows-probe/sliding-assembly-v3-extended.png` and
  `3D-printing/jis80-glass-115-retainer.3mf` unchanged.
- The manual PDF is a separate owner artifact, not the regenerated current
  shop PDF. The latter retains its established local exclusion.
- Saved-file verification: manual PDF parses as 19 A4 pages; PNG signature
  and dimensions valid; 3MF archive CRCs valid and model entries present;
  assembly embedded references inspected. Doctor reports zero active blockers.
- STEP mirror still lists the two owner-resaved assemblies as stale, alongside
  the earlier stage/student queue items. No source CAD was opened, resaved,
  moved or repaired for this commit-only task.
- Deliberate path staging and whitespace check; no software changes or test
  rerun. No Inventor access. No push.
