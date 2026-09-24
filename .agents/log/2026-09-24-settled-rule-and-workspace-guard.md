# Settled rule and workspace guard (pihti-dedup 0.21.1)

**Goal:** two defects from the first real Inventor-repair run on 2026-09-24.

## Decisions

- A referrer whose reference resolved to another file with the same name is
  "not applicable", never "not repaired": the ledger entry is settled when
  every referrer that resolved to the renamed file was repaired and verified.
  The CLI, the toast and `/renames` say "uses another file with this name".
  Today's entry `db32b34a97470796` (Body001.ipt → GX12-nut.ipt, GX12-2
  Jack.iam repaired) was marked settled by hand before this fix.
- Every CLI command refuses a workspace without an `.ipj` file directly in it
  (exit 2) instead of walking whatever folder it was started in; the owner
  had run `rename ... .` from his home directory.
- Implementation by a Sonnet agent; review, gates and commit here.

## Verification

- pytest 344 passed, fresh basetemp; ruff clean; `node --check` clean;
  `git diff --check` clean.

## Next (owner feedback 2026-09-24, going into 0.22.0)

- A top-level assembly lists indirect component names; after a sub-assembly
  repair it still shows the old name until resaved. Suppress those in Doctor
  and say so plainly.
- Reword "Never tracked in reachable Git history" in plain words.
- Duplicates shows byte-identical copies only; same-name/different-bytes
  groups move to Doctor as name clashes with Inventor repair, and
  "Keep only this" / "Quarantine this" leave those rows.
- `.newVer` files are Inventor save leftovers: identical pair → remove the
  leftover only; different pair → never remove, compare in Inventor.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1
  (Sonnet); observed 2026-09-24 JST.
