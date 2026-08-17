# CAD name doctor — pihti-dedup 0.12.0

**Goal:** make same-name repair a persistent session instead of a series of
isolated part pages that lose the final singleton.

## Decisions

- Address a repair session by the ambiguous filename, not by the duplicate
  group's transient hash ID. The session therefore survives each rename and
  continues to show the final original.
- Reuse the guarded rename planner/executor for every member: fixed extension,
  whole-workspace collision checks, sidecar move, where-used evidence, explicit
  silent-rebind confirmation, and durable ledger entry remain unchanged.
- Show the shared filename-based referrers beside copy-ready absolute file and
  folder paths. The tool cannot infer which colliding geometry an assembly
  intended; the owner still opens and repoints it in Inventor.
- Add a strict low-information-name queue for common imported names (`Body`,
  `Part`, `Component`, `Solid`, `Surface`, `Assembly`, `Group`, `Base`,
  `Imported`, and `Model`, with optional numeric suffixes), including singletons.
- Treat `RenameEntry.will_prompt` as rename-time evidence, but calculate the
  page headline from current old-name locations. This lets every Wide Din Clip
  entry become **Inventor will ask now** once the third original is renamed.
- Replace the static quarantine ornament with the live number of recoverable
  files and link it to the recovery ledger.
- Treat geometry previews as required repair evidence: show compact preview
  stacks in both Doctor queues, full previews beside every rename field, and
  previews for referring documents and completed rename history.

## Changed

- Added `/doctor` and `/doctor/name/<filename>` with collision/name queues,
  guarded in-session renames, current status, rename history, and referrer paths.
- Added group-level Doctor links to renameable different-byte collision cards.
- Made `/renames` current-state-aware and linked every entry back to its name
  repair session.
- Updated navigation, recovery status, documentation, styles, tests, and tool
  version 0.12.0.
- Added responsive cached-preview layouts throughout the Doctor without adding
  another renderer or duplicating preview storage.

## Verification

- `pytest`: 196 passed.
- `ruff check`: passed.
- JavaScript syntax check: passed.
- `git diff --check`: passed (line-ending conversion warnings only).
- Live browser: Doctor showed 21 renameable repeated-name sessions and 22
  generic-name sessions. `Wide Din Clip.ipt` showed zero originals, three
  renamed destinations, three referring assemblies, and **Will ask**; all three
  Rename cards likewise showed **Inventor will ask now**. No CAD file was
  renamed during verification.
- Live browser: `Body.ipt` showed seven distinct geometry previews beside the
  seven rename fields and previews for all seven referring assemblies. The
  queue rendered 43 preview stacks / 86 images, no image failed, no horizontal
  overflow appeared, and queue rows remained 68–69 px tall.
