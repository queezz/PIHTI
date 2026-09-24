# Slim rail and machine-local caches (pihti-dedup 0.23.1)

**Goal:** the two follow-ups 0.23.0 exposed: the 3D inspector had no room at
common window heights, and the mesh cache would have lived inside Dropbox.

## Decisions

- Legend is one compact row of the badges themselves with the meaning in each
  tooltip (52 px), the folder note budget is `clamp(4rem, calc(100vh - 46rem),
  8rem)`, and the inspector preview is guaranteed 240 px from 800 px tall.
  Measured at 1920 wide, tops folder card / inspector / legend identical on
  root, folder, search and part pages at every scroll depth: 900 tall
  84/390/775 with a 383×240 preview (was none), 1000 tall 84/390/875 with
  383×331 (was 383×127), 700 tall 84/326/575 with 383×143.
- Preview and mesh caches moved to `cache_root(workspace)` =
  `%LOCALAPPDATA%\pihti-dedup\<folder>-<12 hex of the resolved path>`
  (override `PIHTI_DEDUP_CACHE_ROOT`), refused when the resolved base sits in
  a packaged-app `LocalCache` tree (fleet RULES.md §3). Inventory JSON and the
  quarantine store stay beside the workspace. An old `.pihti-dedup/previews/`
  is ignored and may be deleted. On this machine the root resolves to
  `C:\Users\queezz\AppData\Local\pihti-dedup\PIHTI-45ae879292c8`.
- Implementation by an Opus agent; review, gates and commit here.

## Verification

- pytest 379 passed, fresh basetemp; ruff clean; `node --check` clean on both
  scripts; `git diff --check` clean; strict MkDocs build clean.
- Walk on a scratch copy (port 48981, stopped and port-checked): 457 links
  and assets 200; arrow keys, resize refit, Back/Forward, reload behave;
  folds at 1150 without horizontal scroll. The owner's instance restarted at
  23:42 JST on the uncommitted code and already built the new machine cache.

## Loose ends

- Below about 820 px tall the folder note body collapses to the "Read the
  whole note" link only.
- Git-history previews still cache inside the workspace (directions item).
- The inspector's fact list scrolls inside itself; WEBUI.md's 2026-09-08
  amendment disfavours that; recorded, not changed.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1 (Opus
  implementation); observed 2026-09-24 JST.
