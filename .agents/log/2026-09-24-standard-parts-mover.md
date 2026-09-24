# Standard-parts mover (pihti-dedup 0.16.0)

**Goal:** queezz, 2026-09-24: "I need a helper to move the standard bolts
(most bolts are standard) into my ContentCenter."

## Decisions

- A move is a rename whose folder changes, so it reuses the rename guards and
  the same `.agents/rename-ledger.jsonl`, with `notes` starting
  "standard part → ContentCenter". With unique filenames on, Inventor finds a
  uniquely named moved part by name, so the ledger line carries
  `will_prompt=False` and `/renames` says "Moved; Inventor finds it by
  filename". A same-name file elsewhere makes it a collision decision, not a
  move, and the row points to Collision Doctor.
- Candidates need real evidence: the Inventor `standard` iProperty, an
  explicit standard designation in the name (JIS B, ISO, DIN, ANSI, with a
  number that does not start with 0 so KiCad footprints like `DIN0617` do not
  match), the `ContentCenter/Fastners` naming convention, or a fastener
  description. A loose "contains nut or screw" rule is rejected on purpose:
  `bnc-nut-holder`, `anode-holding-nut`, `Oring_M48-2_nut` are custom parts.
- One confirmed action per row, no bulk move, matching the design doc's
  one-path-at-a-time review. Skip is per tab only.
- Destination is the existing `ContentCenter/Fastners/` spelling.
- Implementation dispatched to an Opus agent; design, review, gates, and the
  commit stayed in the orchestrating session.

## Changed

- `src/pihti_dedup/standard_parts.py` (new): evidence rules, `plan_standard_move`,
  `execute_standard_move`.
- `src/pihti_dedup/renames.py`: `check_filename` extracted; `RenameEntry.is_move`.
- `src/pihti_dedup/cleanup.py`: `execute_survivor_quarantine` for the
  "already in the library, identical bytes" outcome (recoverable quarantine,
  never a delete).
- `src/pihti_dedup/cli.py`: `standard-parts . --dry | --apply --references-checked`.
- `src/pihti_dedup/web.py`: Doctor card "Standard parts",
  `GET /doctor/standard-parts`, token- and loopback-guarded move and
  quarantine POSTs, list memoised per inventory snapshot.
- Templates `doctor.html`, `doctor_standard_parts.html` (new),
  `renames.html`, `base.html`; `dedup.css`, `dedup.js`.
- Docs and version 0.16.0: `README.md`, `.agents/CHANGELOG.md`,
  `.agents/dedup-viewer-design.md`, `pyproject.toml`, `__init__.py`.

## Verification

- pytest 250 passed (235 existing + 15 new), fresh basetemp; ruff clean;
  `node --check` clean; `git diff --check` clean.
- Read-only dry run on the real workspace: 6 candidates, all outcome MOVE
  (two JIS B 1176 bolts in `bellows/`, two ANSI B18.3.4M button-head screws
  in `BoronProbe_2026/parts/`, `M4-Washer.ipt` under TempController, one
  DIN EN ISO 7046-1 screw under LIBS). Nothing was moved.
- Perimeter Walk on a scratch server (port 4191, on a copy of 53 files in
  OS-local scratch): rail pinned at every scroll position and the same x as
  the catalog tree rail; move, cancel, quarantine, skip and restore all
  behave; no sideways overflow at 1400 and 1050px. The port was verified free
  before this commit.
- The owner's `lab pihti` on 4185 was not touched; a restart picks up 0.16.0.

## Next

- Run `Doctor → Standard parts` on the live instance and move the six rows
  one by one; then open the referring assemblies in Inventor once to confirm
  they resolve silently.
- `M2-4_screw.ipt` and `M4×12-VentedHexBolt.ipt` are not proposed (no
  standard property, no description, no designation). The vented bolt is a
  vacuum part anyway; the M2 screw needs an owner call if it should go.
- First Doctor load parses iProperties for ~676 parts (0.8 s once per
  process); warming that in the background ticker would remove the stall.
- Owner request 2026-09-24, next slice: designate hero files and main
  assemblies per folder.

## Usage

- Provider: Anthropic; orchestrator: Claude Fable 5.1; child agents: 1
  (Opus implementation); observed 2026-09-24 JST.
