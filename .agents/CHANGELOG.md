# PIHTI Change History

Shipped archive milestones only. PIHTI does not yet have a formal release/version
contract, so entries are dated rather than assigned software versions. Git history
remains authoritative for exact file changes.

## 2026-08-05

- Shipped `pihti-dedup` 0.1.0: read-only filename-first scanning, Flask review
  UI, portable JSON/CLI output, opt-in Pack-and-Go scope, and compatibility with
  the earlier `scripts/find_duplicates.py` reports. This version labels the tool,
  not the CAD archive. Registered it with lab-cli as `lab pihti`.
- Merged PR #3: non-rotating PIHTI/boron-probe variants, three bearing-support
  design, rear welding spacer, machining drawings, and related component updates.

## 2026-07-09

- Merged PR #2: bellows clamp/linear-guide assembly and its Pack-and-Go workspace.

## 2026-06-22

- Added read-only SHA-256 duplicate inventory tooling, safe cleanup guidance,
  boron-probe integration notes, and Hayashi archive inventories.

## 2026-06-14

- Merged PR #1: initial 2026 boron-probe design and PIHTI integration assemblies.

## 2026-05-22

- Established the curated PIHTI repository front door, generated assembly index,
  MkDocs documentation, and CERN-OHL-W-2.0 licensing.
