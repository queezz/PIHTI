# PIHTI Change History

Shipped archive milestones only. PIHTI does not yet have a formal release/version
contract, so entries are dated rather than assigned software versions. Git history
remains authoritative for exact file changes.

## 2026-08-06

- Shipped `pihti-dedup` 0.8.0: folder notes on Catalog routes are now a
  one-click modal instead of a disclosure → folder page → raw-editor chain.
  Rendered Markdown and the token-protected editor sit side by side, generated
  inventories are readable in place, and ×, **Close**, backdrop click, and
  Escape all dismiss the modal. Save returns to the same Catalog folder and
  automatically reopens the modal with success or validation feedback; the
  dedicated folder page remains an optional full-page link with breadcrumb and
  rail-card exits to the current folder, parent folder, and Catalog home. The
  editor asks for a one-sentence summary below the title, which existing folder
  cards render as their short description. The web app now uses the exact SVG
  favicon configured for local MkDocs.

- Shipped `pihti-dedup` 0.7.2: fixed folder-note Markdown at its source. The
  README generator now refreshes every file that still carries its ownership
  marker, including old generated files that no longer meet today's creation
  heuristic, while marker-free authored notes remain immutable. Its template is
  now a clean generated inventory—title, explanation, main assembly, assemblies,
  and parts—without empty Purpose/Notes/Status headings. A guarded
  `--refresh-only` mode migrated all 36 generated folder READMEs and `INDEX.md`
  without creating new documents. Staging, caches, save history, `Design Data/`,
  and `Templates/` are explicitly excluded.

- Shipped `pihti-dedup` 0.7.1: rendered folder notes now use readable prose
  sizing, heading hierarchy, line length, spacing, and a contained note surface.
  The raw editor explains the small amount of Markdown structure it needs and
  supplies a valid empty-note example. The hand-authored `bellows/README.md`
  was normalized from six unstructured lines—which Markdown correctly collapsed
  into one paragraph—into a heading, purpose paragraph, and labelled fact list.

- Shipped `pihti-dedup` 0.7.0: the Catalog is now a folder-first browser instead
  of one 1,218-tile document sorted by full path. `/catalog` shows the immediate
  top-level systems and root files; `/catalog/<folder>` adds durable drill-down
  URLs, breadcrumbs, immediate child-folder cards with subtree counts, the
  current branch in the stationary rail, and only files directly at that level.
  Large folders and global server-side searches reveal 48 thumbnails at a time
  behind an explicit **Show 48 more** control. Folder notes are folded into the
  current folder and raw editing stays on the dedicated note page. On the live
  workspace the landing response fell from about 956 KB to 57 KB, from 1,218
  file tiles to one root file and 18 system cards; `3D-printing` now sends 48 of
  its 170 direct files until more are requested.

- Shipped `pihti-dedup` 0.6.1: Catalog is now the landing view, including for
  `lab pihti`, and normal tab changes no longer expire a ten-second cache and
  hash the complete CAD tree again. The viewer persists a compact inventory
  under gitignored `.pihti-dedup/`, validates current path/size/mtime metadata,
  and reuses SHA-256 values across Catalog, Duplicates, vendor-scope changes,
  and server restarts. Only new or changed files are hashed; the explicit
  Duplicates Refresh still performs a complete verification. The metadata walk
  itself stopped resolving every already-contained path, reducing the live
  workspace check from about 0.69 s to 0.14 s; after a warm cache and simulated
  restart, both main views rendered in about 0.19 s instead of Duplicates taking
  about 1.8 s to rehash the archive.

- Shipped `pihti-dedup` 0.6.0: the CAD files Inventor never embedded a thumbnail
  into now have previews. About 250 files in this workspace — 166 STL, 57
  STEP/STP, 22 3MF, 6 DWG — showed a grey placeholder in the catalog, the part
  page, and the duplicate rows. STL, STEP, and 3MF are now rendered by an
  in-house numpy z-buffer rasterizer (STEP tessellated through the optional
  `cascadio` extra, staged via an ASCII temp path because OpenCascade cannot
  open a non-ASCII filename), and a DWG reuses the preview AutoCAD already
  stored inside it. Rendering never raises: anything unreadable falls back to
  the same neutral placeholder as before, and an install without the optional
  `preview`/`step` extras degrades to placeholders rather than failing. Because
  a STEP render costs seconds, results are cached on disk under gitignored
  `.pihti-dedup/previews/`, keyed by path, modification time, size, render size,
  and a renderer version, and a new `pihti-dedup warm-previews` builds the whole
  workspace in one pass. `/preview/...` is now exempt from the blanket
  `no-store` header and revalidates by ETag instead, so a browser stops
  refetching hundreds of images per catalog visit. DXF remains uncovered: it
  stores no raster to unpack.

- Shipped `pihti-dedup` 0.5.0: notes are shown rendered instead of as raw text.
  Sidecar prose on a part page, the folder page's note, and an authored folder
  note in a catalog section are rendered server-side with `python-markdown` —
  tables, fenced code, and sane lists, the same engine family as the MkDocs
  site — and the raw textarea moved behind an "Edit raw text" toggle beside it.
  The token-protected save flow is untouched, so the file on disk is still
  exactly what the owner types. Catalog section excerpts are reduced to plain
  text before truncation, so `**bold**` reads as `bold` in a header; a
  *generated* index is deliberately not rendered on the catalog, because it is
  the same file list the thumbnail grid below already shows. Because these are
  files that arrive through student pull requests, the renderer escapes raw HTML
  instead of executing it, drops HTML comments, and strips link schemes other
  than http, https, mailto, and relative.

## 2026-08-05

- Shipped `pihti-dedup` 0.4.1: the folder-note editor was showing a generated
  `README.md`'s leading comment ("Do not edit by hand; re-run the script to
  refresh") right next to the editor's own invitation to edit and save it —
  the wording predated the 0.4.0 contract where editing (by hand or through the
  editor) claims the file as a manual note. The catalog and `/folder/<path>`
  textareas now strip that leading comment block for display when the loaded
  README is still generated, reusing the same stripping `write_folder_note()`
  already applies on save, and both hint labels read "Generated index — edit
  and save to make it your folder note; the generator will then leave this
  file alone." `scripts/generate_readmes.py`'s own comment and blockquote got
  the same correction; the guard only matches the marker's first line, so all
  existing generated READMEs — old or new wording — are still recognised and
  never rewritten.
- Shipped `pihti-dedup` 0.4.0: renaming a CAD file now comes with the memo it
  needs. A new where-used index reads the UTF-16LE reference strings embedded in
  every `.iam`/`.idw`/`.ipn` and answers "which documents name this file?" for
  the whole workspace in well under a second. The part page renames a file in
  place — extension enforced, sidecar carried along — and refuses a new name
  that already exists anywhere in the workspace. When the *old* name survives
  elsewhere, the rename stops and names the assemblies that would silently
  rebind to the wrong file, because `UsingUniqueFilenames=Yes` gives no dialog
  in that case; proceeding takes an explicit second confirmation. Every rename
  appends to the Git-tracked `.agents/rename-ledger.jsonl`, and a new `/renames`
  page turns it into a worklist: old → new, the folder and full Windows paths
  with copy buttons for Inventor's resolve dialog, the referring assemblies as a
  checklist, a clear "Inventor will ask" versus "Inventor will NOT ask" split,
  and a settled toggle written back to the ledger. Folder notes arrived on the
  same release: each catalog section and a new `/folder/<path>` page read and
  edit that folder's own `README.md`, showing an excerpt in the section header,
  and `scripts/generate_readmes.py` now treats the absence of its own marker as
  proof of a manual edit so a saved note can never be overwritten. The catalog
  rail was rebuilt around the owner's rejection of inner scrolling: the scan
  card is pinned at the top and 99 flat folders became a collapsible tree with
  aggregate counts and remembered expansion. Renames are plain filesystem moves
  and nothing is committed automatically.
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
