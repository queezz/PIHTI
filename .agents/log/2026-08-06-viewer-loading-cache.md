# Disk-aware viewer loading — pihti-dedup 0.6.1

**Date:** 2026-08-06
**Agent:** codex gpt-5
**Goal:** make navigation between Catalog and Duplicates responsive, especially
after restarting the local viewer, without hiding real workspace changes.

## Decisions

- Replace the ten-second inventory TTL with metadata validation. Every view sees
  current paths, sizes, and modification times; unchanged files retain their
  known SHA-256 values and only changed files are rehashed.
- Persist compact inventory records in the existing gitignored
  `.pihti-dedup/` cache. Catalog and Duplicates share the same records across
  tabs and process restarts, and vendor scope reuses all overlapping hashes.
- Keep the Duplicates Refresh button as the deliberate full-hash verification.
  Cleanup operations already use that forced path before mutation.
- Make Catalog the root route, brand destination, and `serve --open` target. The
  duplicate review remains one top-level tab rather than the launch surface.
- Avoid resolving every scanner path repeatedly. `os.walk` already yields paths
  below a resolved root without following directory symlinks, so the common
  relative-path operation can stay lexical and fall back to resolution only for
  an exceptional outside path.

## Changed

- `src/pihti_dedup/web.py` — persistent, disk-aware, incremental inventory cache;
  Catalog root route.
- `src/pihti_dedup/inventory.py` — faster contained-path handling.
- `src/pihti_dedup/cli.py`, `templates/base.html` — Catalog launch and branding.
- `tests/test_web.py`, `tests/test_cli.py` — restart reuse, one-file invalidation,
  vendor-scope reuse, and Catalog launch coverage.
- `README.md`, `.agents/CHANGELOG.md`, `.agents/dedup-viewer-design.md` — operating
  contract and shipped behavior.
- `pyproject.toml`, `src/pihti_dedup/__init__.py` — 0.6.1.

## State

- Live workspace metadata scan: 0.694 s before, 0.140 s after.
- Live Duplicates route: about 1.85 s on the old cold path; about 0.20 s after a
  simulated restart with the persistent inventory. Catalog was about 0.19 s.
- `pytest -q -p no:cacheprovider`: 167 passed.
- `ruff check src tests scripts/find_duplicates.py`: clean.
- `git diff --check`: clean.
- `mkdocs build --strict`: clean, with output directed to machine-local scratch.
- No server was started and no CAD file was modified.

## Next

- No loading-cache follow-up is required. If path/size/mtime validation itself
  becomes visible on a much larger archive, measure before adding an OS watcher;
  the current check is exact, portable, and sub-0.2-second on this workspace.
