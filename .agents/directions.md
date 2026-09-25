# Directions

Forward-looking work only. Move completed outcomes to `CHANGELOG.md` and keep
session evidence in `log/`.

## Inventor versions across machines

- Install the latest Inventor 2026 update on the second box, move that box to 2027, or keep every Inventor save on the 2027 machine — the owner's call.
  The main workstation saves with Inventor 2027.1; the second box runs 2026
  with no update installed, and a 2026 cannot open a file that 2027 saved.
  Stakes: every part or assembly saved on the 2027 machine can no longer be
  opened on the 2026 box, neither in Inventor nor through the tool, so the
  mirror export, the Doctor fixes and the rename repair for those files run
  only on the 2027 machine, and the list grows with every save there. Six
  files were in that state on 2026-09-25: `bellows/bellows.iam`,
  `ContentCenter/Electrics/gx12-aviation-connectors/GX12-2 Jack/GX12-2 Jack.iam`,
  `ElectronicsBox/esp32-ambient-logger/STEPs/OLED 2.42 12864 v7/pcb.iam`,
  `Plasma Vessel/Oring-probe-flange-with-GV.iam`,
  `Plasma Vessel/Plasma-vacuum-cross/UFC-152.ipt`,
  `Plasma Vessel_2026/contents/ICF114-through.ipt`.
  Recommendation: install the current Inventor 2026 update on the 2026 box
  first; Inventor's own refusal says a 2026 with the latest updates opens
  parts and assemblies one year newer. If bellows.iam still refuses, move that
  box to 2027.
  Safe default: nothing changes on disk. The 2026 box keeps exporting and
  repairing files saved by 2026 or older; the six 2027 files fail to open there
  until they are handled on the 2027 machine.

## Dedup viewer — next review slice

- Which of the two temperature-controller folders is the live one,
  `ElectronicsBox/TempController` or `ElectronicsBox/TempController-v2`? They
  share 22 byte-identical files and differ in 63 — awaiting the owner.
  Stakes: until this is known the 22 identical copies cannot be quarantined
  and the Body.ipt collisions in both trees stay on the Doctor page.
  Recommendation: `TempController-v2` is the newer tree (fan, LRS-150 supply,
  thermocouple socket) and looks like the one that was built; keep it.
  Safe default: nothing is removed; both trees stay as they are.
- **Collapse vendor import bundles.** The 49 generic names live in 11 STEP
  import folders. Doctor should show each bundle as one item with the
  re-import instruction (import the vendor STEP as a single named part) and a
  "vendor import, leave alone" disposition, instead of 49 single renames.
  Prepare short role-based name suggestions per bundle for the owner to
  confirm (owner, 2026-09-24: "shorter meaningful names are better").
- **Git-history previews still cache inside the workspace**
  (`.pihti-dedup/git-previews/`). 0.23.1 moved previews and meshes to the
  machine-local cache root; move this one the same way.
- Laptop and phone layouts are deferred by owner decision 2026-09-24: the
  viewer targets a desktop window beside Inventor (about 1400–2560px wide),
  with one safety fold below 1200px.

- **DXF has no preview.** 0.6.0 covers STL, STEP, 3MF, and DWG; the six
  scanner-visible `.dxf` files still show the neutral placeholder. A DXF is a
  text vector format with no embedded raster, so unlike DWG there is nothing to
  unpack — it would need an actual 2D renderer (`ezdxf` plus a matplotlib or
  Pillow backend). Decide whether six files justify a third rendering path.
- Partly done in 0.3.0: per-file metadata sidecars (`<cad filename>.md`) now
  record intent next to the CAD file. Still open is the *review* disposition —
  a per-group record of `canonical` / `keep-both` / `needs-inventor` /
  `package-baggage` keyed to a stable group signature, which the duplicate
  screen can read back.
- Show an existing sidecar's status and tags in the duplicate rows and catalog
  tiles, so a reviewed file is visibly reviewed without opening its page. The
  0.4.0 folder-note excerpt does this for folders; files are still open.
- Done in 0.4.0: filename collisions are linked to a machine-read “where used”
  answer. `src/pihti_dedup/whereused.py` scans the embedded UTF-16LE reference
  strings, the part page lists the referring documents, and a rename records
  them in the ledger. Still open is confirming that read against Inventor's own
  Design Assistant on a sample, and surfacing where-used counts on the duplicate
  rows so a collision can be triaged without opening each member.
- Renames recorded in `.agents/rename-ledger.jsonl` stay unsettled until every
  referring assembly has been opened and repointed. Work the `/renames` page
  down to zero unsettled entries before the next submission review.
- Decide whether same-stem/different-extension families belong in the main review
  UI or a separate related-artifacts view.
- Add an “open containing folder” action only with a strict localhost boundary
  and a test proving requests cannot escape the configured workspace.

Implemented architecture and baseline: `dedup-viewer-design.md` and
`log/2026-08-05-pr-orientation-and-dedup-viewer.md`.

## Submission curation

- Open the three `bellows/*.iam` assemblies in Inventor and identify the primary
  assembly before pruning the PR #2 package.
- Decide whether `_2026` assemblies are intentionally self-contained snapshots or
  should consume canonical shared parts from `ContentCenter/` and established
  system folders.
- Review same-name/different-content component groups before choosing a canonical
  path, especially `ICF70_to_KF40.ipt`, `UFC-152.ipt`, and generic imported names
  such as `Body.ipt`.

## Documentation

- Capture PR #3's useful non-rotating-system figures and explanation in durable
  repository documentation rather than leaving the only explanation in the PR.
- Add a short submission-manifest convention: primary assembly, project file,
  new parts, reused parts, exports, and one overview image.
- Keep `INDEX.md` navigational. A folder `README.md` is now the folder-note
  surface as of 0.4.0: saving one through the viewer strips the generator marker
  so `scripts/generate_readmes.py` leaves it alone from then on. Broader design
  intent still belongs in `docs/`.

## Release/version policy

PIHTI remains an unversioned engineering archive. `pihti-dedup` has its own tool
version because it is installable; that version does not label CAD. Before
publishing a stable fabrication snapshot, define what constitutes a release and
where immutable release artifacts live.
