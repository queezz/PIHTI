# Dedup UI, PR review, and guarded cleanup

## Goal

Correct the duplicate viewer to the fleet/Paperlib web shell, make it useful for
reviewing newly merged student PRs one folder and one member path at a time, and
add preview-first cleanup for merge-added exact copies.

## Decisions

- Use Paperlib's Duplicates screen and `.folder-grid` / `.folder-panel` layout as
  the named precedent. The top bar names the view; there is no second page title,
  large dashboard summary, or explanatory card stack.
- Use two fixed-width rails beside the results on wide Inventor PCs. Both have a
  sticky top equal to their initial page offset and no internal scrollbar. They
  stack after the results on narrower screens.
- Put duplicate counts in rail buttons that actually filter the list. Render
  group kinds as flat colored metadata rather than pill-shaped pseudo-controls.
- Copy one project-relative member path per row. Remove group-level bulk copy.
- Read recent first-parent `Merge pull request #N from ...` commits locally and
  associate current duplicate groups with CAD paths changed by each merge.
- Keep zero-result folders and PR merges visible: a clean result is useful review
  evidence and should not disappear from the selector.
- Dry cleanup targets only merge-added members of same-name exact-copy groups
  when an identical survivor exists outside the merge. Modified paths,
  renamed-only matches, and all-merge groups are protected.
- Actual cleanup is explicit and recoverable: require `--apply
  --references-checked` or the equivalent localhost/token web confirmation,
  revalidate the signed preview, quarantine files, write a restoration manifest,
  and rescan. Never permanently delete CAD.
- Reuse the byte-identical favicon from `2024-interactive-diagram`.
- Render and copy project paths with Windows separators, and show modified time
  beside size and hash for every member.
- Add a per-member **Delete** action only for byte-identical groups. Confirmation
  names the selected path and survivor; execution revalidates path, size,
  modified time, and hash before moving the file to recoverable quarantine.
- Characterize the seven observed base/`*.newVer.ipt` pairs separately. All have
  identical bytes and timestamps, but the producing application is not proven.
- Re-read Paperlib's actual duplicate flow after the first PIHTI deletion reset
  the working list. Paperlib v1.11.1 explicitly persists kind and text across a
  trash/reload. PIHTI now persists its full filter context, retains the old list
  during refresh, anchors an unaffected group at the same viewport offset, moves
  focus forward, and reports success with a fixed toast.
- Add a fleet-style `README_SHORT.md` as a pasteable cold-session route. Keep
  `AGENTS.md` authoritative and link to fleet context after PIHTI-specific files
  instead of copying house rules into another drifting document.

## Changed paths

- `src/pihti_dedup/git_history.py`
- `src/pihti_dedup/cleanup.py`
- `src/pihti_dedup/cli.py`
- `src/pihti_dedup/inventory.py`
- `src/pihti_dedup/web.py`
- `src/pihti_dedup/templates/base.html`
- `src/pihti_dedup/templates/duplicates.html`
- `src/pihti_dedup/templates/_results.html`
- `src/pihti_dedup/static/dedup.css`
- `src/pihti_dedup/static/dedup.js`
- `src/pihti_dedup/static/favicon.ico`
- `tests/test_cleanup.py`
- `tests/test_cli.py`
- `tests/test_git_history.py`
- `tests/test_web.py`
- `pyproject.toml`
- `src/pihti_dedup/__init__.py`
- `README.md`
- `README_SHORT.md`
- `AGENTS.md`
- `.agents/README.md`
- `.agents/commit-culture.md`
- `.agents/CHANGELOG.md`
- `.agents/dedup-viewer-design.md`
- `.agents/directions.md`
- `.gitignore`

The owner's explicitly applied PR #1 cleanup quarantines 40 validated
merge-added exact copies. During implementation the action was initially
misread as accidental and restored after a complete hash check; the same dry
plan was then revalidated and intentionally reapplied. The current restoration
manifest is
`.pihti-dedup/quarantine/20260805T070304Z-pr-1/manifest.json`.

## Verification

- External `pihti-dedup` environment: 28 tests passed; `ruff check
  src/pihti_dedup tests` clean; changed Python files pass `ruff format --check`.
- `git diff --check` passed; MkDocs built with `--strict`.
- Before cleanup, the real PIHTI scan had 1,259 CAD files and 113 displayed
  groups. After the confirmed PR #1 quarantine it has 1,219 CAD files, 64
  repeated-filename groups, and 9 renamed-copy groups (73 displayed groups).
- PR #1 apply verification: 40 manifest entries, 0 SHA-256 mismatches, 0 source
  paths left in the workspace, and 0 missing named survivors.
- The owner then individually quarantined
  `BoronProbe_2026/parts/B_probe_bearing_without_holes.ipt`. Manifest
  `.pihti-dedup/quarantine/20260805T074859Z-member-43adc635/manifest.json`
  verifies byte-for-byte, the original is absent, and its named survivor exists.
  Current scan: 1,218 CAD files, 63 repeated-filename groups (35 exact, 28
  collisions), and 9 renamed-copy groups; Git shows 41 intentional CAD
  deletions in total.
- Browser check at desktop width: the rail top remained at 84 px before and
  after a 780 px page scroll.
- PR #3 filter showed 9 duplicate groups. PR #2 remained selectable with 0.
- A member-row action copied one path and changed only that button to `Copied`.
- Browser regression check: `Exact + ElectronicsBox + .ipt + Body` remained a
  9-group result after rescan; group `23ea2f65bd071df1` stayed at 38 px and
  `scrollY` stayed 842.67. The same filters survived a full reload.
- Browser console reported no errors.

## Next steps

- Let the owner review the corrected workflow through `lab pihti`.
- Add a tested manifest-based restore command before broadening cleanup scope.
- After every applied cleanup, open the affected top-level assemblies in Inventor
  and verify reference resolution.
