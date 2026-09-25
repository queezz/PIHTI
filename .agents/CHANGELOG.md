# PIHTI Change History

Shipped archive milestones only. PIHTI does not yet have a formal release/version
contract, so entries are dated rather than assigned software versions. Git history
remains authoritative for exact file changes.

## 2026-09-25

- Shipped `pihti-dedup` 0.24.2: `step-mirror sync` no longer stops the whole
  batch on the first file Inventor is slow to answer for. After a timeout it
  probes the session once; if Inventor answers, the batch continues past that
  one file (left as `timeout`) instead of abandoning everything still queued.
  Only a session that genuinely stops answering (a modal dialog left open)
  still stops the batch, and the CLI now says so on its own line
  (`stopped: Inventor is not answering (a dialog may be open) · N not
  started`, exit 1); a batch that runs to the end with some failures lists
  them by path and outcome after the counts.
  The viewport also tessellates STEP finely now (a bolt thread that looked
  like a low-polygon export was the viewer's own coarse setting; the stills
  stay coarse), and cached meshes rebuild on next view.

- Shipped `pihti-dedup` 0.24.1: the STEP mirror index is swapped into place
  with a short retry, because Dropbox holds a freshly written file for a
  moment and the first real `step-mirror sync` lost one index write to that
  lock (the exports themselves were unaffected).

- Shipped `pihti-dedup` 0.24.0: the STEP mirror. Every Inventor part and
  assembly in the default scan scope gets a STEP copy, exported by Inventor
  itself into the sibling folder `PIHTI-step` beside the workspace (override:
  `PIHTI_DEDUP_STEP_MIRROR`), outside the workspace and outside git, carried by
  Dropbox, regenerable. Each copy is the source's name plus `.step`
  (`lp-box.iam.step`), because seven folders hold a part and an assembly with
  one stem. `mirror-index.json` records the source state each copy came from.
  While the viewer runs with Inventor open, a background job exports one stale
  or missing file per refresh, oldest first, skipping files open in Inventor
  and backing off a minute after a failure; nothing runs without Inventor. The
  3D view now turns `.ipt` and `.iam` files from their current STEP copy; the
  inspector offers "export now" when there is none, the part page's File card
  names the copy's time, and a quiet "STEP mirror N / M" in the top bar opens
  a page listing missing and stale copies and the last exports. The CLI has
  `step-mirror status`, `sync [--budget-seconds N] [--launch]`, and `export`.
- Shipped `pihti-dedup` 0.23.2: the inspector's still-to-3D swap no longer
  visibly jumps. The WebGL viewport reads its clear colour from the preview
  box's own CSS background instead of Inventor's light-blue (which never
  applied to an STL/3MF/STEP still in the first place), fits its home camera
  to the mesh's actual projected outline rather than its bounding box's
  corners so the swap does not change scale, and reveals the canvas only
  once its first frame has actually rendered. Heavy meshes load faster and
  further: the binary drops its per-triangle normals by default (a browser
  derives a flat normal on the GPU from screen-space derivatives instead;
  `?normals=1` still serves the older payload for one that cannot), which
  lifts the cap from 400,000 to 2,000,000 triangles, and above about 5 MB in
  flight the inspector names the download ("Loading 3D · N MB") beside the
  still image while it waits.

## 2026-09-24

- Shipped `pihti-dedup` 0.23.1: the inspector's preview gets real room. The
  Legend is one compact row of its nine badges, wrapping to two rows, each
  badge's meaning in its tooltip; the folder note's budget in the left rail is
  now `clamp(4rem, calc(100vh - 46rem), 8rem)`; the inspector keeps a preview
  area at least 240 px tall on any window 800 px tall or more, which the 3D
  view fills, with the file's facts scrolling below it. At 1920 wide the 3D
  view is 383×240 at 900 px tall (none before), 383×331 at 1000 px (383×127
  before), and 383×143 at 700 px. Previews and meshes move out of the
  workspace and out of Dropbox to a machine-local cache root,
  `%LOCALAPPDATA%\pihti-dedup\<workspace-id>\` (`~/.cache/pihti-dedup/...`
  elsewhere, `PIHTI_DEDUP_CACHE_ROOT` to override); a root that resolves into
  a packaged app's private AppData tree is refused. `warm-previews` and the
  viewer print the root they use. The old `.pihti-dedup/previews/` is no
  longer read and can be deleted.
- Shipped `pihti-dedup` 0.23.0: an STL, 3MF, or STEP file turns in 3D. In the
  catalog inspector and on the part page its still preview gives way to a
  WebGL view on Inventor's light-blue backdrop, in the same isometric home
  view: drag to turn, wheel to zoom toward the pointer, right-drag or
  Shift-drag to pan, double-click to return home. The mesh is fetched only for
  the file the inspector shows, after it has rested there for 150 ms, from a
  new `/mesh/<path>` route that reuses the preview loader, caches a compact
  binary under `.pihti-dedup/meshes/`, and refuses meshes above 400,000
  triangles; the still image stays whenever there is no mesh and says why in
  one line. `warm-previews --meshes` builds every mesh once. Folder pages now
  show every file they hold; only archive-wide search keeps **Show 48 more**,
  which now lands on the first tile it reveals.
- Shipped `pihti-dedup` 0.22.0: Duplicates lists byte-identical files only.
  A same-name group with mixed bytes shows each identical set as its own
  group with the guarded Delete; a member whose bytes match nothing is not
  listed, and same-name/different-bytes groups move to Doctor, counted in the
  rail as "N name clashes → Doctor". Doctor's name session leads each member
  with the rename and its Inventor repair; consolidating different-byte
  revisions stays behind a closed "Consolidate after comparing in Inventor"
  section, and "Keep only this" / "Quarantine this" are gone. `.newVer` files
  are named for what they are, Inventor save leftovers: an identical one is
  offered only **Remove leftover**, and one that differs from its original,
  or has none, is listed under Doctor's **Interrupted saves** to compare in
  Inventor, never removed. After a repair, a top-level assembly that names
  the renamed part only indirectly is recorded as `indirect` and stops
  showing a missing name until Inventor saves it again; the workbench shows
  renamed destinations without a click. The Renames page reads at a glance: a
  one-line head per entry with its state, referrers with badges, copy-ready
  paths beside them, a settled filter in the rail, and the green repaired
  state for any repaired entry. The Git-history answer and the folder-card
  flag are reworded in plain words: "No commit of this repository ever had a
  file with this name", and "cover" (the sidecar key stays `featured`, with
  `cover: true` read the same).

- Shipped `pihti-dedup` 0.21.1: two fixes from the first real repair run. A
  referrer whose matching descriptors all resolved to another file keeping
  the old name (`no-descriptor`) was counted as unrepaired; it is not
  applicable to the rename and no longer blocks `settled`, `will_prompt`, the
  CLI exit code, or the web toast — it is reported as "uses another file with
  this name" instead of "not repaired". Every workspace-taking subcommand
  (`scan`, `serve`, `merge-cleanup`, `warm-previews`, `meta seed`,
  `standard-parts`, `notes check`, `rename`) now refuses a folder without an
  `.ipj` file at its root before walking anything, so pointing the tool at
  the wrong directory fails fast instead of scanning it.

- Shipped `pihti-dedup` 0.21.0: a rename can repair its referring assemblies
  through the running Inventor session, without Design Assistant. Inventor
  opens each referrer invisibly before the file moves, repoints the matching
  references to the new file, saves with `Save2(False)`, and reopens to
  verify; a document already open in Inventor is skipped and named. A
  fully repaired rename is recorded settled, and the where-used index drops the
  old name the saved assemblies still carry as a fossil string. Every Inventor
  call runs on a worker with a progress timeout, so an open dialog produces a
  "did not answer" message instead of a hung page. Doctor name sessions and the
  part page offer the repair when Inventor is running; the CLI twin is
  `pihti-dedup rename <path> <new name> --repair [--dry]`. Needs the new
  `inventor` extra.

- Shipped `pihti-dedup` 0.20.2: the stylesheet and script URLs carry the
  file's modification time, so a viewer update is a new URL in every browser
  (a Firefox-based browser kept the old stylesheet through a hard refresh);
  a current version is cached as immutable, anything else stays `no-store`.

- Shipped `pihti-dedup` 0.20.1: every file tile is one grid column wide. A
  file with a description or sidecar prose no longer becomes a two-column
  image-and-story card, which stretched its whole grid row to its own height;
  the text takes at most two clamped lines under the name, with the whole text
  in its tooltip (a Description also fills the inspector's Description row).
  The tallest row on `ContentCenter/Aluminium-profiles` measures 251px at
  1920 wide.
- Shipped `pihti-dedup` 0.20.0: sourcing notes. A folder's bought parts and
  the options for them live in `<folder>/sourcing/`, one Markdown note per
  option (title, vendor, part number, link, price, status, the folder's CAD
  files it is for, date, then free prose), with pictures and PDFs in
  `sourcing/attachments/`. **Sourcing** in the top bar lists every option in
  the archive grouped by status (`candidate`, `quoted`, `ordered`,
  `received`, `rejected`); each folder has its own page of option cards with
  pictures inline, a Status card to narrow them, and **Add option**. The
  editor has the fields as inputs, the folder's CAD files as checkboxes, a
  live preview, and paste or drop of a picture or PDF into the text to
  attach it. The folder card in the catalog carries one Sourcing line at a
  fixed height, a file named by an option gets a `sourced` badge (now in the
  Legend, which grows by one row), and the inspector states the option
  titles. `notes check` also reports a sourcing note that does not parse or
  whose status is not one of the five. Notes are never committed and
  deleting an option is not built.

- Shipped `pihti-dedup` 0.19.2: word badges instead of corner dots. Every
  tile mark is now a short lowercase word in a small tinted box, in the hue
  it already had: `clash` (same name, different bytes), `copy` (identical
  copy elsewhere), `renamed` (same bytes, other name), `unhashed` (same
  name, bytes not compared), `generic` (generic name), `newer` (a newer file
  with this name exists), `main` (main assembly), and `featured`. They sit in
  a row under the tile's size line, never over the preview; each badge's
  tooltip carries the long meaning. When one tile's badges wrap, the whole
  grid row gets the taller badge row, so size lines stay level. The inspector,
  the part page's File card and toggles, and the Legend use the same badges;
  the Legend keeps each meaning beside its badge and stays at one height and
  one place on every catalog and part page.

- Shipped `pihti-dedup` 0.19.1: one fixed legend and the placement toggles in
  the inspector. The left rail's last card is now **Legend** on every catalog
  and part page, always listing every mark in the same order, so it no longer
  changes size or moves between pages. The folder card keeps one height, so
  the inspector's top and the legend's top stay at the same place on every
  page at a given window height. The inspector carries **Make main assembly**
  and **Feature on folder card** at its foot for the file it shows; setting
  acts at once, clearing asks with the file's name, and the page returns to
  the same folder with the tile focused. The part page lists the file's own
  marks in its File card and keeps its toggles.

- Shipped `pihti-dedup` 0.19.0: featured files and smaller main assemblies.
  A second sidecar flag, `featured: true`, puts a file at the front of the
  preview strip of every folder card above it, without a place among the main
  assemblies. Heroes and featured files are set and cleared only on the part
  page, with **Main assembly** and **Feature on folder card** side by side;
  clearing either asks first. The inspector no longer has a hero button and
  states "Main assembly" and "Featured" as facts. **Main assemblies** tiles are
  file-tile size, and on the root page each names its folder as a link with an
  **Open folder** action beside it. Every tile mark is now a dot in the
  tile's top-right corner in one order (copies, generic name, newer file,
  hero, featured), matching the legend; the coloured tile edges and the gold
  left bar are gone. After the manual picks, a folder card's strip goes
  round-robin across its subfolders, taking each one's best representative:
  a top-level assembly, then any assembly, then a part, then an export with a
  cached render, largest first.

- Shipped `pihti-dedup` 0.18.1: one icon for the browser tab, the top bar, and
  the MkDocs site: a bold P drawn as a path on a navy tile, legible at 16px.
  The old icon set five letters in two fonts and two low-contrast colours.

- Shipped `pihti-dedup` 0.18.0: `pihti-dedup notes check .` is the gate for
  a visual pass (`.agents/visual-pass.md`): it reports an authored folder note
  that still carries the generator marker, an authored note whose first line
  under the title is not a summary sentence, and a metadata sidecar whose
  frontmatter does not parse. Read-only; exit code 1 when anything is found.

- Shipped `pihti-dedup` 0.17.0: main assemblies. Any file can be marked a
  hero with one click, either with **Set hero** in the catalog inspector or on
  its part page. The mark is `hero: true` in the file's metadata sidecar. A
  missing sidecar is created from iProperties, and an existing one changes by
  that one line. A folder's heroes lead its page as a **Main assemblies** row
  of double-width tiles, and they are not repeated among its files. The catalog
  root lists every hero in the archive with its folder. Folder-card strips
  start with the heroes below them. A gold bar on the tile's left edge marks a
  hero, and the legend explains it. The folder note in the left rail now shows
  its authored part as rendered Markdown in a fixed space, so the inspector
  below it stays in the same place on every folder. A longer note fades out and
  opens in a reader, with **Edit** for the editor. The top bar no longer shows
  a count of recoverable files; the Removed page's History rail holds that
  count.
- Shipped `pihti-dedup` 0.16.0: a helper moves standard fasteners into
  `ContentCenter/Fastners`. Doctor has a fourth card, **Standard parts**, with
  the candidate count. Its page lists every `.ipt` outside the library that has
  a `standard` iProperty, a JIS, ISO, DIN, or ANSI designation in its name, the
  library's naming convention, or a fastener description. Each row shows that
  evidence, the destination, and the number of referring documents. A uniquely
  named part moves with one confirmed **Move**, because Inventor finds it again
  by filename. The move is recorded in the rename ledger, and `/renames` shows
  it as a move. A byte-identical copy already in the library can be sent to the
  recoverable quarantine with its survivor named. A name that exists elsewhere
  is refused and links to Collision Doctor. **Skip** hides a row for the current
  browser tab. `pihti-dedup standard-parts . --dry` prints the same table, and
  `--apply --references-checked` runs only the plain moves.
- Shipped `pihti-dedup` 0.15.0: the catalog is thumbnail-first. Catalog and
  part pages share one three-column layout: a wide left rail with folder or
  file facts, the folder note behind a **Note** button, a hover and keyboard
  inspector, and a legend for the tile marks; the thumbnails in the middle;
  and the folder tree on the right. Both rails stay pinned at every scroll
  depth, and a long tree scrolls inside its own card. One line above the
  thumbnails holds the breadcrumb and an instant filter, and Enter still runs
  the global search. Folder cards carry a strip of six previews from their
  subtree and sit in their own grid, with the folder's files in a separate
  grid below. File tiles are marked for same-name collisions, identical
  copies, same-bytes copies under another name, generic names, and newer
  same-named files, all derived from the existing inventory. At the root,
  the `PIHTI.ipj` project file stands in the rail instead of a tile. Preview
  URLs carry a version key from the file's stat, so the browser keeps an
  unchanged preview for a year and fetches a changed one at once. Catalog
  pages may be reused for five seconds, and hovering a folder link
  prefetches its page. The part page packs the preview, iProperties, and mass
  into one sheet, with Where used and the sidecar side by side and rename
  behind a disclosure.
- Shipped `pihti-dedup` 0.14.0: the viewer now serves every page from an
  in-memory snapshot of the workspace instead of walking the filesystem on
  each request. A background refresher revalidates the snapshot every few
  seconds while someone is browsing (about once a minute when idle), hashing
  only new or changed files, and swaps the new snapshot in atomically. The
  persisted inventory under gitignored `.pihti-dedup/` is adopted immediately
  on startup, so a restart is not a cold start. The where-used index, the
  filename-location map Doctor uses, and the merged-PR history from Git are
  refreshed the same way, so Doctor and Duplicates no longer pay their own
  walk or a git subprocess per page. Every mutation still revalidates the
  live disk synchronously before acting and invalidates the snapshots
  afterwards; Duplicates' **Refresh** remains the explicit forced full
  verification. `pihti-dedup serve --refresh-seconds N` sets the period; `0`
  restores the previous validate-on-every-request behaviour, which is also
  the default for `create_app()` in tests. The directory walk itself was
  rewritten on `os.scandir` with string paths (130 ms → 38 ms on the
  1,182-file workspace), and the where-used walk got the same treatment.

## 2026-08-06

- Shipped `pihti-dedup` 0.13.0: Doctor now starts from an assembly workbench
  instead of forcing imported geometry through a global filename queue. Each
  `.iam` workbench shows its direct embedded missing, ambiguous, and generic
  names; previews every current candidate; keeps the assembly path and safe
  Inventor sequence visible; and returns guarded renames to the same assembly
  context. Missing references query every reachable Git ref by exact filename.
  The inline history distinguishes never-tracked import/vendor dependencies
  from repository files, previews historical Inventor geometry, and identifies
  rename destinations that still exist with a copy-ready current path.

- Shipped `pihti-dedup` 0.12.0: the new **Doctor** view turns filename repair
  into a persistent session. Collision groups and generic imported names such
  as `Body001.ipt` open by filename, keep every remaining original visible
  through sequential guarded renames, retain the renamed destinations, and put
  the shared referring assemblies beside copy-ready file and folder paths. The
  rename ledger now reports what Inventor will do from the live workspace rather
  than freezing its headline at rename time, while preserving a note when that
  outcome changed. The static **Local quarantine** label is replaced by a live
  recoverable-file count linking to Removed.

- Shipped `pihti-dedup` 0.11.0: manually reviewed different-byte collisions can
  now remove one selected revision or be consolidated around one explicitly
  chosen survivor. **Quarantine this** removes only its row; **Keep only this**
  revalidates the survivor and every candidate, then moves the non-survivors
  and their metadata sidecars to the sibling `PIHTI-quarantine/runs` store, and
  records old path → survivor, hashes, possible filename-based referrers, and
  recovery manifest in a durable consolidation ledger. The searchable
  **Removed** view answers later missing-path questions, old part URLs explain
  where the file went, and a guarded Restore action returns the complete event
  to its original paths. Rows in merged-PR top-level folders now carry an orange
  PR badge and edge marker so submission material is identifiable at a glance.
  Pre-existing files merely edited by a PR receive a neutral history badge,
  distinct from the orange deletion-candidate treatment.
  Cleanup actions optimistically remove the affected row/card, stale inventory
  requests cannot repaint older HTML over the result, and a repeated action
  from another stale tab resolves to the existing recovery event instead of an
  alarming missing-group error. Removed-path and survivor contrast is balanced.
  Removed events are compacted into ten-minute cleanup sessions with collapsible
  bodies and a status/action rail. The merged-PR reset is labelled **No PR
  filter**, matching its actual behavior rather than implying a union filter.

- Shipped `pihti-dedup` 0.10.2: duplicate rows distinguish the two Windows Open
  dialog targets. **Copy folder** supplies the directory accepted by the address
  bar; **Copy file path** supplies the complete path for the bottom **File name**
  field. Inventor's address bar can navigate to the containing directory but
  rejects a file path even when that file is visibly present there.

- Shipped `pihti-dedup` 0.10.1: duplicate-row Copy now places the complete
  absolute Windows path on the clipboard. Inventor's Open dialog interprets a
  relative path from its current folder, not from the active project workspace.

- Shipped `pihti-dedup` 0.10.0: folder notes now open in a larger, browser-resizable
  workspace. Preview and editor scroll independently, so Save and Close remain
  available for a long note, and the preview safely re-renders Markdown as the
  owner types without saving. Restored the Inventor project's workspace display
  name to `Workspace`; its actual workspace remains the repository root (`.`).

- Shipped `pihti-dedup` 0.9.0: metadata now tells the story directly in the
  Catalog. Sidecar prose and useful Inventor Description values produce wide
  image-and-story file cards; status, tags, material, and nonredundant Part
  Numbers appear as compact chips. Metadata-poor files remain small, and
  iProperties are cached until the source file's size or modification time
  changes. Authored folder summaries use taller, multiline cards, the current
  folder summary is promoted into its heading, and the Catalog root shows the
  repository README's opening purpose statement.

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
