# Dialog-free exports, readable sync, leftover closing (pihti-dedup 0.24.4)

**Goal:** three things from the owner's first mirror runs on 2026-09-25:
Inventor raised Resolve Link and Non-Unique Project File Names dialogs while
assemblies were opened invisibly for export; the CLI printed one unreadable
full path per file; timed-out exports left assemblies open invisibly, and the
next sync refused them as "open in Inventor".

## Decisions

- An `.iam` is skipped as `needs-doctor` before it is opened when one of the
  names it embeds (minus the pairs the ledger records as repaired or indirect)
  exists two or more times in the workspace, or is missing AND is the old name
  of a rename still open in the ledger. The literal rule "any missing name"
  would have skipped all 239 assemblies, because the byte scan also lists
  fossils such as `Standard (mm).iam` and import source names; with the
  narrowed rule 27 are skipped today (`board.ipt` bundles, the Wide Din Clip
  referrers, the GX12 and SSR `Body*.ipt` bundles). A rename made outside
  the tool can still raise Resolve Link; the 0.24.2 timeout path covers it.
  `--force` exports one named file regardless.
- `sync` prints one line per folder, then counts including "N need Doctor",
  then failures and needs-Doctor entries by short name; `--verbose` restores
  one line per file. Every attempt goes to `<mirror>/export.log` with the
  full path (rotated at 5 MB); the `/step-mirror` page reads that log's tail
  and lists "Needs Doctor" with links to the Doctor name page.
- A timed-out export records its document in `pending-close.json`; every
  sync, export, export-now and background tick first closes such documents,
  only when they have no window and no other open document uses them (a part
  loaded under the owner's open assembly has no window of its own), logged
  as `closed-leftover`. The four leftovers from today were closed by hand
  through the session before this landed (67 invisible documents, none with
  a window).
- Implementation by an Opus agent; review, gates and commit here.

## Verification

- pytest 439 passed, fresh basetemp; ruff clean; `node --check` clean;
  `git diff --check` clean; strict MkDocs build clean.
- Mirror state after the owner's runs: 904 of 908 exported; the four left are
  the dialog assemblies, now to be listed as needs-Doctor.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1 (Opus
  implementation); observed 2026-09-25 JST.
