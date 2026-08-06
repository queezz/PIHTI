# Directions

Forward-looking work only. Move completed outcomes to `CHANGELOG.md` and keep
session evidence in `log/`.

## Dedup viewer — next review slice

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
- Write quarantine outside the Inventor workspace by default — owner decided
  2026-08-06: default store is `../PIHTI-quarantine/runs/<stamp>-<source>/`
  (sibling of the repo, Dropbox-synced, not a git repo). The store already has
  this layout with a root `README.md` explaining restore paths; the tool still
  defaults to the in-workspace `.pihti-dedup/quarantine/` and must be updated
  to match. Keep `.pihti-dedup/previews/` (cache) where it is — it is not CAD.
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
- Add a tested restore command for `.pihti-dedup/quarantine/` manifests before
  expanding cleanup beyond the guarded merged-PR exact-copy operation.

Implemented architecture and baseline: `dedup-viewer-design.md` and
`log/2026-08-05-pr-orientation-and-dedup-viewer.md`.

## Submission curation

- Open the three `bellows/*.iam` assemblies in Inventor and identify the primary
  assembly before pruning the PR #2 package.
- Verify that the bellows assemblies do not depend on the bundled `Design Data/`
  or `Templates/`, then plan removal of vendor/package baggage and the path-bearing
  `packngo.log` as a separate reviewed change.
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
