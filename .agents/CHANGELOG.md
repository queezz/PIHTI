# PIHTI Change History

Shipped archive milestones only. PIHTI does not yet have a formal release/version
contract, so entries are dated rather than assigned software versions. Git history
remains authoritative for exact file changes.

## 2026-08-05

- Shipped `pihti-dedup` 0.3.0: the viewer now reads Inventor documents directly.
  A pure-Python MS-OLEPS parser extracts iProperties and the preview image that
  Inventor already embeds, with no Inventor, COM, or Windows API involved. Every
  duplicate member row, a new `/catalog` thumbnail grid, and a new `/part/<path>`
  page show that preview, so same-name collisions can be triaged visually. Part
  pages report part number, description, material, designer, subtype, and the
  saving Inventor build, flag a Part Number that disagrees with the filename, and
  withhold mass properties unless Inventor's own validity flag vouches for its
  cached values. Added portable metadata sidecars — `<cad filename>.md` with YAML
  frontmatter plus prose — seeded from iProperties one file at a time in the
  viewer or in bulk with `meta seed --dry|--apply`. Sidecar writes reuse the
  localhost-and-token boundary, refuse frontmatter that does not parse, and are
  never committed automatically.
- Quarantined 41 confirmed byte-identical copies from merged submission trees as
  a separate CAD cleanup: 40 merge-added PR #1 members and the individually
  reviewed `BoronProbe_2026/parts/B_probe_bearing_without_holes.ipt` member.
  Every removed path had a hash-identical surviving copy; recovery remains
  available from Git history and the local quarantine manifests.
- Shipped `pihti-dedup` 0.2.0: split the wide-screen review context across two
  stationary rails without internal scrollbars; added the established
  `2024-interactive-diagram` favicon; and added dry-run plus guarded, recoverable
  quarantine for exact copies introduced by merged PRs. Member rows now show
  modified time and valid Windows paths, exact-byte members have an individually
  confirmed Delete-to-quarantine action, and `*.newVer.ipt` pairs are separately
  characterized without asserting unproven Inventor provenance. Following
  Paperlib's duplicate-session precedent, all review filters now survive delete,
  rescan, and reload; fragment refreshes preserve the visible group and scroll
  position, while success uses a non-layout-shifting toast. Added a fleet-style
  `README_SHORT.md` cold-start route and clarified the authoritative rule order.
- Shipped `pihti-dedup` 0.1.1: corrected the viewer to the fleet/Paperlib shell,
  kept the right rail stationary, moved counts into actionable rail filters,
  added project-folder and local merged-PR analysis, and changed copy behavior
  from whole groups to one member path at a time.
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
