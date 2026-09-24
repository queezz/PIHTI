# 2026-09-24 — Duplicates only, save leftovers, indirect names (pihti-dedup 0.22.0)

## Goal

The owner's live review of 2026-09-24: Duplicates had moved past "same name,
maybe a duplicate" and still offered deletions on unrelated same-name parts;
`.newVer` files were called "origin unproven"; a repaired sub-assembly left its
top assembly showing a missing old name; "Never tracked" read as jargon; the
Renames page was precise but unreadable at a glance on a wide monitor; and the
folder-card flag word "featured" said nothing.

## Decisions

- Duplicates reads `Inventory.duplicate_groups`: exact name groups, one exact
  group per shared hash inside each collision group (`split_groups`, found by
  id through `find_group` so the guarded Delete works), and renamed groups.
  Collision and unverified groups stay in `summary`, the JSON export and the
  catalog badges; the rail points at them with "N name clashes → Doctor".
- The reviewed consolidation endpoint is unchanged and reachable only from a
  closed "Consolidate after comparing in Inventor" disclosure in the Doctor
  name session. "Keep only this" and "Quarantine this" are gone.
- `.newVer`: base looked up in the same folder. Identical bytes and modified
  time → a leftover card with one quiet **Remove leftover** on the leftover
  row, no action (not even Rename) on the base. Different bytes, or no base →
  Doctor's **Interrupted saves**, no action. Identical bytes with different
  modified times stay an ordinary renamed group (none exist today). The
  explanation is stated once per page, on the first leftover card; the others
  carry it as the label tooltip (Teaching law: one explanation per concept).
- `indirect` in the ledger: a `no-descriptor` referrer, when at least one
  referrer was repaired, is indirect only if none of its old-name descriptors
  resolved to a surviving copy. `RepairResult.elsewhere` carries that fact
  from the session. Without it, a collision rename (Body001.ipt) would have
  marked every assembly using another Body001.ipt as indirect and hidden its
  real reference. `renames.settled_pairs` feeds repaired and indirect pairs to
  `build_index` in the web app and the CLI.
- The two 0.21.0 ledger lines the owner asked about (Part5.ipt, Body001.ipt)
  have no `indirect` field; they load unchanged, so their top assemblies keep
  their cards until resaved or until the field is added to those lines by
  hand. Deriving it from the frozen note would misclassify the Body001 case.
- Renames page: one head line per card, a state badge, a 70rem two-column
  body, middle-ellipsized path lines with the full path in the tooltip, and a
  settled filter in the rail (remembered in local storage). Recorded repair
  fields decide the green state; an entry with none keeps the live banner.
- "cover" is the visible word for the folder-card flag; the sidecar key stays
  `featured`, `cover: true` is read as a synonym, clearing removes both. The
  Main assemblies row leaves out its own `main` badge; the inspector fact and
  tiles elsewhere keep it.

## Changed paths

- `src/pihti_dedup/`: `inventory.py`, `cleanup.py`, `inventor_session.py`,
  `renames.py`, `cli.py`, `sidecar.py`, `web.py`, `__init__.py`,
  `static/dedup.css`, `static/dedup.js`, templates `_results.html`,
  `_file_tile.html`, `doctor.html`, `doctor_name.html`,
  `doctor_assembly.html`, `part.html`, `renames.html`
- `tests/`: `test_inventory.py`, `test_web.py`,
  `test_inventor_repair_flow.py`, `test_sidecar.py`
- `pyproject.toml`, `README.md`, `.agents/CHANGELOG.md`,
  `.agents/dedup-viewer-design.md`, `.agents/directions.md`

## Verification

- pytest 360 passed (344 kept, intent-preserving updates to 15; 16 added);
  ruff clean; `node --check` clean; `git diff --check` clean.
- Perimeter Walk on a scratch server: synthetic workspace outside Dropbox
  with the real ledger lines copied in, Inventor connection stubbed to none,
  port 48972, stopped by tree kill and verified free; the owner's 4185
  listener untouched. Tool clicks do not land under viewport emulation in the
  browser pane (pointer events arrived at about 5x the target coordinates), so
  navigation used `element.click()` and `history.back/forward`, and all
  measurement was DOM-based.
  - Duplicates: no collision card, rail "All / Identical copies / Same bytes,
    other name" plus the clash link; rail 84px at 0–75% scroll at 1000 and
    700; at 100% the Folders rail (857px with 19 synthetic folders) releases at
    its container end, unchanged by this work (the new link row is 1px
    shorter than the removed Collisions button). Remove leftover ran end to
    end with its confirmation and toast.
  - Doctor: Interrupted saves first; `#name-clashes` lands 84px (22px below
    the 62px bar) after adding `scroll-margin-top`, which it lacked; Back and
    Forward return to the same states; every link 200.
  - Doctor name session: three "Review rename" forms, disclosure closed by
    default, consolidation ran end to end and the notice names the kept file.
    Its rail rests at 201px and pins at 84px, as recorded in 0.21.0.
  - Workbench: Renamed destinations open with rows visible.
  - Renames at 1920 and 2560 wide, 1000 and 700 tall: every head line 21px,
    every card 1120px (70rem), centred, no horizontal overflow, rail 84px at
    every scroll depth, deep-link reload lands the card at 158px, settled
    filter 13 / 11 / 2.

## Next steps

- Add `"indirect": [...]` by hand to the Part5.ipt and Body001.ipt ledger
  lines if the owner wants those top-assembly cards gone before the next
  Inventor save, naming only the assemblies that hold the name indirectly.
- The perceptual-preview idea from the removed directions item (same name,
  same picture → resave; different picture → clash) is not built.
