# STEP mirror action workflow (pihti-dedup 0.29.0)

**Goal:** Make stale, missing, and reference-blocked STEP work understandable
and actionable without hunting through Catalog and collapsed Doctor controls.

## Decisions

- A source belongs to one queue: safe missing/stale files are ready to export;
  assemblies with ambiguous or absent references are blocked.
- Ready rows state the condition and expose Export or Re-export while Inventor
  is available. Blocked rows state the referenced child, matching paths, and
  the Doctor decision needed.
- STEP context follows navigation to the file and Doctor pages. Doctor shows
  complete paths, explicit rename labels, and the compare-and-keep section.
- A successful rename carries the renamed source's existing STEP to its new
  mirror path. Existing STEPs for assemblies Inventor saved and reopened are
  advanced to the verified file state: reference-name-only saves do not create
  a cascade of stale/blocked work.
- A deleted Git-history occurrence reads its preview from the deleting
  commit's parent, where the file still exists.

## Changed paths

- `src/pihti_dedup/web.py`
- `src/pihti_dedup/git_filename_history.py`
- `src/pihti_dedup/templates/step_mirror.html`, `part.html`, `doctor_name.html`
- `src/pihti_dedup/static/dedup.css`
- `tests/test_step_mirror.py`, `tests/test_web.py`, `tests/test_doctor_fix.py`,
  `tests/test_git_filename_history.py`
- `pyproject.toml`, `src/pihti_dedup/__init__.py`, `README.md`
- `.agents/CHANGELOG.md`

## Verification

- Focused STEP mirror, web, Doctor, and Git-history suite: 247 passed; the
  final targeted rename/history regressions: 8 passed.
- Full suite: 498 passed. Ruff, both JavaScript syntax checks,
  `git diff --check`, and strict MkDocs build passed.
- Scratch `lab start pihti --port 4199 --refresh-seconds 0` used isolated
  runtime, logs, cache, and STEP mirror roots. The owner service on 4185 was
  not operated. The scratch process was stopped and 4199 had no listener.
- Perimeter Walk in the live DOM covered every top tab; ready-file and blocked
  Doctor deep links; reload; all three page anchors; and
  1700×1000 and 1700×700 viewports. Both sticky rails stayed at 84 px across
  the full 66,000 px scroll range. Ready and Blocked landed 23 px below the
  fixed chrome; Last exports remained visible at the bottom boundary. Browser
  console had no warnings or errors.
- The walk caught the four-column rule losing to the later generic Doctor row
  rule, which put Export under the thumbnail. The selector was strengthened;
  live measurement then showed thumbnail, file, diagnosis, and action in four
  columns. A scratch index also proved the rendered stale state, timestamps,
  Re-export action, and stale file-page notice.
- Regression tests cover deleted-file historical blobs and conservative STEP
  carry-forward (an absent prior STEP is never claimed). Applying the new
  carry-forward rule to today's completed ledger entries changed the live
  mirror from 898 current / 6 stale / 6 missing / 9 blocked to 908 current /
  0 stale / 2 missing / 2 blocked. No CAD source was written by that repair.

## Next

- Resolve the two genuinely missing-reference assemblies in Doctor.

## Usage

- Provider: OpenAI; agent: Codex GPT-5; child-agent count: 0; provider usage:
  unavailable.
