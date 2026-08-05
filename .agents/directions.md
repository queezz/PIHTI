# Directions

Forward-looking work only. Move completed outcomes to `CHANGELOG.md` and keep
session evidence in `log/`.

## Dedup viewer — next review slice

- Add an optional, portable review sidecar for human dispositions without moving
  CAD or turning scan results into a database.
- Link filename collisions to a recorded Inventor/Design Assistant “where used”
  check; hash differences alone remain insufficient evidence.
- Decide whether same-stem/different-extension families belong in the main review
  UI or a separate related-artifacts view.
- Add an “open containing folder” action only with a strict localhost boundary
  and a test proving requests cannot escape the configured workspace.
- Add a CLI twin, complete preview, reference review, and recoverable quarantine
  before considering any mutating web action.

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
- Keep `INDEX.md` and generated folder READMEs navigational; design intent belongs
  in `docs/` or a concise hand-authored README.

## Release/version policy

PIHTI remains an unversioned engineering archive. `pihti-dedup` has its own tool
version because it is installable; that version does not label CAD. Before
publishing a stable fabrication snapshot, define what constitutes a release and
where immutable release artifacts live.
