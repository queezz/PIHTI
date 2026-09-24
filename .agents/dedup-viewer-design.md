# Dedup Viewer Design

## Status

The read-only first slice shipped as `pihti-dedup` 0.1.0 on 2026-08-05. Version
0.1.1 corrected the working shell against the fleet/Paperlib precedent and added
local merged-PR and folder analysis. Version 0.2.0 split the context across two
stationary rails and added preview-first, recoverable cleanup for exact copies
introduced by a merge. Version 0.3.0 added embedded-thumbnail reading, a catalog
and part page, and portable metadata sidecars. Version 0.4.0 added the where-used
index, the guarded rename action with its ledger and `/renames` memo page, folder
notes on the folder's own `README.md`, and a collapsible catalog folder tree. The
shared scanner lives in
`src/pihti_dedup/inventory.py`; the CLI and Flask viewer consume the same
classifications, and `scripts/find_duplicates.py` remains a compatibility entry
point for earlier reports.

Version 0.6.1 makes the catalog the landing surface and replaces the viewer's
ten-second inventory TTL with disk-aware reuse. Each request performs a cheap
metadata walk; if paths, sizes, and modification times match, the existing
inventory and hashes remain authoritative. The compact records persist under
gitignored `.pihti-dedup/`, so a process restart does not imply a rehash. New or
changed files alone are hashed, the vendor superset borrows every digest from
the default scope, and the explicit Duplicates Refresh remains a forced full
verification. This is intentionally separate from the preview cache: inventory
records classify duplicate bytes, while preview records cache rendered pixels.

Version 0.7.0 replaces the flat all-files catalog with progressive disclosure.
`/catalog` is the workspace level and `/catalog/<folder>` is a durable
master/detail route: breadcrumbs and the rail locate the current folder, compact
cards expose only immediate children, and the thumbnail grid contains only
direct files. Global search is server-side rather than a filter over a prebuilt
page, and both search and large leaf folders reveal 48 records at a time. The
current tree ancestry opens on the server; unrelated expansions are deliberately
not remembered, so the rail cannot accumulate into a second full catalog.

Version 0.14.0 replaces the per-request walk with a snapshot model: the
inventory, the where-used index, Doctor's filename-location map, and the
merged-PR history from Git are each built once and served from memory instead
of being recomputed per page. A background refresher revalidates the snapshot
every `--refresh-seconds` while someone is browsing (a few seconds; about once
a minute when idle), hashing only new or changed files and swapping the result
in atomically. The persisted records under gitignored `.pihti-dedup/` are
adopted immediately on startup, so a restart is not a cold start. Mutations —
rename, quarantine, restore, consolidation — still revalidate live disk
synchronously before acting and invalidate every snapshot afterwards;
Duplicates' **Refresh** remains the explicit forced full verification. This
supersedes the 0.6.1 per-request metadata walk described above; passing
`--refresh-seconds 0` restores that validate-on-every-request behaviour and is
still the default for `create_app()` in tests.

Version 0.15.0 makes the catalog thumbnail-first and changes its contract.
Catalog and part pages use one grid, `25.5rem minmax(0, 1fr) 17rem`, inside a
page that may now grow to 2400px. On a 1920px screen that gives a 408px left
rail, a 1141px centre column, and a 272px tree rail. The tree rail sits at the
same x-position and width as the outer Duplicates rail, and both rails and the
header line share the sticky offset `calc(var(--bar-height) +
var(--content-pad))`. `scrollbar-gutter: stable` keeps short pages from
shifting the rails by the scrollbar width. The left rail holds the folder or
file facts with a copy-path action, the **Note** button that opens the existing
note modal with a two-line excerpt beneath it, the root workspace summary and
`PIHTI.ipj` project-file line, an inspector for the hovered or arrow-focused
tile, and a legend for the tile marks present on the page. The right rail holds
only the folder tree. Above the thumbnails is one line: the breadcrumb and a
filter field. The field filters the cards already on the page in one animation
frame. Enter, or **Search whole archive**, submits the unchanged `?q=` search.
Folder cards have their own grid, with a 22.5rem minimum card width and a 3 x 2
strip of 110px-minimum thumbnails. Each strip is built server-side in one pass
over the inventory (`folder_strips`), with Inventor documents first. The
folder's files follow in a separate grid under a compact `Files · N` line. File
tiles carry a hidden fact list, rendered from cached iProperties and the
where-used snapshot only when there is something beyond name, size, and chips;
the inspector copies it. Nothing floats over the grid. Tile marks
(`file_signals`) come from the inventory's filename and renamed groups and the
generic-name rule, memoized per inventory object like the folder index.
Copies colour the top edge in the Duplicates palette; a generic name or a newer
same-named file adds a dot. The newer-file mark is filesystem evidence only and
names the folder of the newer file. An "unused part" mark was not added:
top-level assemblies and standalone parts are legitimately unreferenced, so it
would mark much of the archive.

Every rendered preview URL carries `v=<mtime_ns>-<size>-r<renderer>`
(`preview_url`, a Jinja global). A request whose key matches the file's fresh
stat, and which yields a real preview, answers `private, max-age=31536000,
immutable`. A missing or stale key, or the placeholder, keeps the `no-cache`
plus ETag path, because installing a preview extra turns a placeholder into an
image without touching the file. Plain catalog pages (no `q`, no `saved`) answer
`private, max-age=5` instead of `no-store`, so the page `dedup.js` prefetches
after a 100ms hover on a tree link, breadcrumb, or folder card serves the click
that follows. Five seconds cannot show anything staler than the snapshot the
page is rendered from, which the ticker refreshes on about that period.

Owner rulings of 2026-09-24 shape this layout. A pinned rail outranks the
earlier rejection of an inner scrollbar. So the tree card and the left rail are
capped at `calc(100vh - var(--bar-height) - var(--content-pad) -
var(--page-foot) - 1px)`, the room between the sticky offset and the page foot,
and only the tree or the inspector's fact list scrolls inside them. Capping at
the full viewport was not enough: a taller card is pushed up by its own grid
area at the end of the scroll, measured at 50px on a 700px window. The viewer
is a desktop tool used beside Inventor at 1400-2560px. It has one fold below
1200px, where both rails move into one static right column and the inspector is
dropped. Laptop and phone layouts, and the cookbook's narrow-screen checks
beyond that fold, are deliberately deferred for this project rather than
skipped.

Version 0.16.0 adds a helper that moves standard fasteners into
`ContentCenter/Fastners` (`src/pihti_dedup/standard_parts.py`, Doctor's
**Standard parts** page, and `pihti-dedup standard-parts`). Only `.ipt` files are
proposed, and only with named evidence. The evidence is one of four kinds: the
`standard` iProperty that Content Center writes; an explicit JIS, ISO, DIN, or
ANSI designation in the filename; the library's exact naming convention; or a
fastener description. A designation number must not start with 0, which keeps
KiCad footprints such as `R_Axial_DIN0617_...` out. Custom parts whose names
merely contain "nut" or "screw" are never proposed. `ContentCenter/`, `STEPs`
import trees, and `OldVersions/` are excluded. The move rests on the resolution
rule above. With unique filenames on, an assembly whose stored path fails
searches the project for the filename, and exactly one match binds without a
dialog. Moving a uniquely named part therefore changes its folder and nothing
Inventor resolves by, so every referring assembly opens as before. A same-named
file anywhere else would make that search ambiguous. So a move is refused
whenever the name exists elsewhere, including a different-byte file already in
the library, and the row links to Collision Doctor. The one exception is a
byte-identical copy already at the destination. Then nothing needs to move, and
the stray copy goes to the recoverable quarantine used by member cleanup, with
the survivor named. Execution revalidates the file's size, modification time,
and hash, and rebuilds the collision map, before acting. A move is `Path.rename`
plus the sidecar. It appends a rename-ledger line with the same filename,
`will_prompt` false, and a note starting "standard part → ContentCenter", and
`/renames` shows it as a move. The owner confirms every row separately; there
is no bulk action in the viewer, and the CLI's `--apply --references-checked`
runs only the plain moves, never the quarantines. **Skip** hides a row for the
current browser tab only.

Version 0.17.0 lets the owner mark main assemblies. A hero is a flag in the
file's metadata sidecar: `hero: true`, the seventh frontmatter key. Any
Inventor document or export can carry it, and a folder may have several. The
sidecar is used because it is the one metadata surface already accepted: it is
portable, tracked in Git beside the CAD file, and never committed for the
owner. The toggle is `POST /part/<path>/hero`, guarded by loopback and the form
token like the other writes. The form states the value it wants, so a repeated
submit cannot flip the flag back. With no sidecar, one is seeded from
iProperties exactly as **Create metadata** seeds it, plus `hero: true`.
Clearing a flag on a file with no sidecar writes nothing. With a sidecar, the
text is parsed first, and a sidecar that does not parse is refused. The edit is
then one line: `hero: true` goes in before the closing fence, or the `hero:`
line comes out. Other keys, their formatting, the line endings, and the prose
stay byte-for-byte. If that one-line edit ever fails to give the intended
frontmatter, only the frontmatter is re-serialised. The toggle returns to the
page it was pressed on. In the catalog that is the `#file-...` anchor of the
tile, which is focused and shown in the inspector, with a toast naming the
file. The query that carries the toast is removed from the address, so a reload
or Back does not repeat it. Heroes lead a folder's page as a **Main assemblies**
row of double-width tiles. Each tile shows the preview at up to its own pixel
size, the name, Description, and size. Heroes are left out of the files grid
and its count. The root lists every hero in the archive with its folder.
Folder-card strips start with the subtree's heroes in path order. The tile mark
is a gold bar down the left edge, a shape and hue no other mark uses. The
inspector's first fact for a hero is "Main assembly". The lookup is memoized
per inventory object and per disk-validation serial, a counter
`InventoryCache` bumps on every validation. The serial is needed because an
unchanged disk keeps the same `Inventory` object, and a sidecar is not part of
the inventory. So the lookup is redone once per snapshot refresh: one `stat` per
record, about 14 ms for this archive's 1182 records. A sidecar is read only
when its size or modification time has changed.

The same release changes the folder note in the catalog's left rail. The
authored part of the note is shown as rendered Markdown: everything above the
generator's inventory (`## Main Assembly`, `## Assemblies`, `## Parts`, and
its notice), without the leading title. It sits inside a fixed budget of
`clamp(5rem, calc(100vh - 42rem), 11rem)`. That is 11rem on any window taller
than about 850px, and the same on every folder at a given window height. So the
inspector's top edge does not move with the note's length. A note that does
not fit is cut with a fade. **Read the whole note** opens the modal as a
reader: the rendered note alone, at a reading measure. **Edit**, beside the ×,
swaps in the previous preview-and-editor view. A save reopens the reader, and a
refused save reopens the editor with the draft. The inspector sizes its preview
to the room the capped rail has left above the title and a few fact lines, so a
short window never pushes the shown file out of the rail. The top bar no longer
counts recoverable files. That number lives only in the Removed page's History
rail, and the per-request manifest read that fed the old indicator is gone.

Version 0.19.0 revises this on the owner's review. Main-assembly tiles are one
file-tile column wide with the file tile's 4:3 preview. Links cannot nest, so
each is a card holding the part link (preview and name) and, on the root page,
the folder path as a link plus **Open folder**; the folder's own page omits
both. Coloured tile edges, including the gold left bar, were removed at the
owner's request because they read as an editing or selection state; that
device comes from lecturedeck, which is not a webui model (fleet `RULES.md`
§10). Every signal is now a 9px dot in the tile's top-right corner, in one
order shared by the tile, the inspector facts, and the legend: collision,
exact, renamed, unverified, generic (a ring, so it does not read as renamed),
newer, hero, featured. A second flag, `featured: true`, has the same one-line
set and clear and the same seeding, and is read in the same `stat` pass as
`hero`. The flags are set only on the part page (`POST /part/<path>/hero` and
`/featured`); clearing asks for confirmation, and the inspector states facts
only. Folder-card strips are manual first: heroes below the card, then featured
files, each in path order. The rest go round-robin across the card folder's
subfolders in name order, then its direct files, each round taking the best
remaining representative: a top-level assembly (no referrer in the where-used
snapshot), any assembly, a part, another Inventor document, then an export
whose render is cached; larger first, then path order. A subfolder a manual
pick came from sits out the rounds it covered, and anything unranked only tops
up a short strip. Strips are memoised per folder while the inventory, the
where-used snapshot, and the flag lookup are unchanged.

## Purpose

Provide a local, human-in-the-loop view of filename collisions and byte-level
duplicates across the active PIHTI Inventor workspace. The viewer helps select
what to inspect in Inventor; it does not infer geometry equivalence or silently
rewrite assembly references.

## Inventor rule that drives the design

`PIHTI.ipj` defines workspace `.` and sets `UsingUniqueFilenames` to `Yes`.
Autodesk documents that, when a stored reference cannot be found, Inventor
searches the project structure for a unique file with that referenced filename.
If more than one match exists, resolution becomes ambiguous and Inventor asks the
user to choose.

Therefore the first question is not “which files share a hash?” but “which exact
filenames occur more than once inside this project?” Hashes classify the risk:

1. **Same filename, same hash** — redundant byte-identical copies. A likely
   consolidation candidate after reference review.
2. **Same filename, different hash** — an Inventor-resolution collision and the
   highest review priority. It may be a revision, resave, or unrelated geometry.
3. **Different filename, same hash** — storage duplicate/rename evidence, but not
   a filename-resolution collision.
4. **Same stem, different extension** — usually a native/drawing/export family.
   This is deliberately deferred to a related-artifacts view so it cannot be
   confused with a duplicate claim in the first slice.

Current tracked-CAD baseline, excluding `OldVersions/` and the bellows vendor
support trees: 1,259 files; 104 repeated-filename groups covering 229 files; 76
groups are byte-identical and 28 contain multiple blobs.

## Implemented first slice

### Data layer

Extract the inventory/grouping logic from `scripts/find_duplicates.py` into a
small importable module while keeping the script's CLI behavior. Records retain:

- project-relative path
- exact filename and case-folded filename key
- suffix, size, and modification time
- SHA-256
- top-level system/submission folder
- exclusion reason, when filtered from the default scope

Scanning defaults to Inventor/CAD extensions and skips `.git`, `_site`, caches,
`OldVersions`, and ignored staging. Vendor `Design Data/` and `Templates/` are a
toggleable scope, not mixed into the default engineering results.

The scan result is disposable and rebuildable. No database is needed; JSON is
appropriate for export/debugging, but generated mechanical reports should not be
committed on every scan.

### Web layer

Follow paperlib's proven shape, specifically its Duplicates screen and
`.folder-grid` / `.folder-panel` working shell:

- Flask, server-rendered HTML, progressive enhancement, no frontend framework.
- `GET /duplicates` returns an immediate shell whose top bar names the view; do
  not repeat that identity with a large page heading or introductory block.
- `GET /duplicates/results` performs or retrieves the scan asynchronously and
  returns the result fragment.
- The result fragment begins with one shared three-column grid: results plus two
  fixed-width rails. Both rails start at their sticky offset, never move when the
  page scrolls, and never get an internal scrollbar. On narrower screens they
  stack after the results.
- Default bind is `127.0.0.1`. Actual cleanup is localhost-only; the remaining
  routes are read-only.
- Client-side text and kind filters operate on the loaded groups without rescans.
- Follow Paperlib's `pl-dup-filter` decision: persist the complete working review
  context in local storage and reapply it after every async fragment replacement.
  PIHTI includes text, kind, folder, merged PR, extension, cross-folder, and
  vendor scope rather than only Paperlib's kind and text.
- Colored group counts in the rail are buttons because they filter. Group state
  inside result cards is plain text/icon metadata, not button-like pills.
- Every member row has its own copy-path action. There is no group-level bulk
  copy because the Inventor review proceeds one path at a time.
- Member paths are rendered and copied with Windows separators. Rows show the
  local modified time as evidence alongside size and a short hash.
- A cleanup/rescan keeps the old list visible but dimmed while the fresh scan is
  fetched. It restores an unaffected visible group to the same viewport offset,
  moves keyboard focus to that group's next action after a deletion, and uses a
  fixed toast for success. Do not prepend a notice or replace the working list
  with a spinner during a mutation; both cause avoidable spatial resets.

Primary filters:

- filename collision / exact copy / renamed copy
- project folder
- recent merged PR, derived from local first-parent Git history
- extension
- cross-folder only
- include vendor/package data

Each group shows its filename, classification, copy count, distinct-hash count,
sizes, modified times, and separate absolute file/folder paths for Inventor's
File name field and address bar. The two right rails
hold actionable kind, folder, and merged-PR selectors plus compact scan
statistics. Zero-result folders and PRs remain visible because absence of
duplicate evidence is itself useful after a merge. An “open containing folder”
action can be localhost-only; opening the actual assembly remains an Inventor
operation.

### Merged-PR cleanup

`merge-cleanup --pr N --dry` and the web preview share one planner. Candidates
must be same-name, byte-identical files added by that merge, with at least one
current identical survivor outside the merge. Modified paths, renamed-only hash
matches, and groups whose every copy came from the merge are protected.

Actual execution requires `--apply --references-checked` or the equivalent
localhost-only, token-protected web confirmation. It re-scans, compares the dry
plan signature, verifies every candidate's path, size, modified time, and SHA-256, then moves
files to `.pihti-dedup/quarantine/<timestamp>-pr-N/`. A JSON manifest records
original paths, surviving copies, hashes, and the required post-apply Inventor
assembly check. A mid-operation failure rolls moved files back.

### Individual exact-copy cleanup and `newVer`

Every member of an exact or renamed exact-byte group may be explicitly selected
with **Delete**. The confirmation names that Windows path and at least one
byte-identical survivor. The localhost/token-protected endpoint force-rescans,
compares a signature covering path, size, modified time, and SHA-256, and moves
the one selected member to recoverable quarantine with its own manifest.
Different-byte collisions never receive this action.

Seven current renamed-copy groups match `name.ipt` plus `name.newVer.ipt`. In
all seven, the two files have identical SHA-256 values and identical filesystem
modified timestamps. The UI characterizes these as **newVer pairs** but says
“origin unproven”: neither the bytes nor the timestamp establishes that Autodesk
Inventor created the suffix, and no Autodesk documentation for it was found.

### Catalog, part page, and metadata sidecars

Version 0.3.0 adds a document-reading layer beside the filesystem scanner.
`src/pihti_dedup/inventor_meta.py` parses the MS-OLEPS property sets inside
`.ipt`/`.iam`/`.idw`/`.ipn` with `olefile` only — no Inventor, COM, or Windows
API. Inventor scrambles its property-stream names, so sets are matched by FMTID
and never by stream name; PID 255 carries each set's own name as the fallback for
an unknown FMTID. Design Tracking ids were cross-checked against this workspace,
and Mass/SurfaceArea/Volume/Density (58/59/60/61) were confirmed arithmetically
because `Mass == Volume * Density` on every part carrying all three. Mass
properties are a cached snapshot, so they are reported only when `Valid
MassProps` (PID 62) is present and non-zero.

Thumbnails are the preview image Inventor already embedded; nothing is rendered.
`GET /preview/<repo-relative-path>` resolves the path, refuses anything that does
not stay inside the workspace, and serves the bytes with a content type taken
from the image magic. Old headerless DIB previews get a BITMAPFILEHEADER
prepended. A process-local cache keyed by path and modification time holds both
hits and misses. Of 999 Inventor documents in the current workspace, 996 carry a
PNG preview; the three STEP-imported parts without one get a neutral inline SVG
placeholder rather than a broken image.

`GET /catalog` is the top-level system index; `GET /catalog/<folder>` shows one
folder's immediate children and direct files; and `GET /part/<repo-relative-path>`
shows one file's preview, iProperties, file facts, and sidecar. All use the
established shell with a single rail. The part page states a Part Number that
disagrees with the filename, because Inventor resolves references by filename
and the mismatch is real evidence: 227 of 999 documents disagree today.

A metadata sidecar is `<cad filename>.md` — the whole filename plus `.md`, so a
part and its drawing never collide — holding YAML frontmatter
(`part_number`, `material`, `status`, `tags`, `supersedes`,
`seeded_from_iproperties`, and since 0.17.0 `hero`) and free prose. Seeding copies iProperties and leaves
judgement blank. Writes reuse the loopback-plus-token boundary of the cleanup
endpoints, validate that the frontmatter parses before touching the file, and
never commit: a sidecar simply appears as an untracked or modified file. The CLI
twin is `meta seed --dry|--apply`, which seeds only Inventor documents in bulk
because no other CAD extension carries iProperties.

### Where-used index, rename, and the rename memo

Version 0.4.0 answers the reference question the earlier slices deferred.
`src/pihti_dedup/whereused.py` reads the raw bytes of every `.iam`/`.idw`/`.ipn`
and pulls out the UTF-16LE reference strings Inventor stores there, walking back
from each CAD extension to the nearest path separator. Only the filename is kept,
because unique-filename resolution ignores the stored path. The workspace's 305
referring documents index in about 0.2 s cold and 0.06 s warm behind a cache
keyed by path and modification time. The index deliberately skips `OldVersions/`
— a referrer is a document the owner would actually open — while the collision
map behind renames deliberately includes it, because Inventor's filename search
reaches everything under the workspace.

Renaming turns on one asymmetry in Autodesk's search rules. If a referring
document's stored path fails and **no** file with that filename exists, Inventor
raises the resolve-link dialog and the user can paste a path. If **another** file
with that filename exists, Inventor binds to it silently: no dialog, no warning,
and an assembly that now consumes the wrong geometry. So:

- A new name already present anywhere in the workspace is refused outright; it
  would manufacture a fresh collision.
- An old name that survives elsewhere after the rename stops the operation, names
  the surviving copies and the assemblies that would rebind to them, and requires
  a second explicit confirmation. The plan is rebuilt on that confirmation.
- Paths past 260 characters, changed extensions, reserved device names, and
  case-only changes are refused. Case-only is refused on purpose: Inventor
  matches filenames case-insensitively, so it resolves identically and would
  write a misleading ledger entry.
- Only the four Inventor extensions can be renamed, because they are exactly the
  set the index and the collision map cover.

The rename is `Path.rename` and nothing else. The `<filename>.md` sidecar moves
with it. Git is untouched; the moved file and the ledger line appear as ordinary
changes in the owner's own commit.

`.agents/rename-ledger.jsonl` is the durable record — Git-tracked, machine-facing
JSON per the `.agents/` artifact convention, one appended line per rename holding
timestamp, old and new workspace-relative paths, both filenames, the where-used
list at rename time, `will_prompt`, and `settled`. Paths are workspace-relative
so no machine-specific path is committed; `/renames` builds the absolute Windows
paths at render time for its copy buttons. That page separates the two flavours
explicitly — "Inventor will ask — paste this path" versus "Inventor will NOT ask
— open these and repoint manually" — lists the referring assemblies as a local
checklist, and writes only the settled toggle back to the ledger.

### Folder notes

A folder's note is its own `README.md`, not a parallel store, so it is the same
file MkDocs and GitHub already show. `scripts/generate_readmes.py` had written an
autogen notice since the beginning but never read it back: it skipped every
existing README by mere existence, which was safe but left the marker
decorative and any future refresh free to destroy notes. That marker is now
load-bearing. `is_manually_edited()` reports true whenever a README does *not*
open with the marker — which covers a hand-authored file, a rewritten generated
one, and an unreadable one — and every write in the generator goes through one
guard that consults it. Saving a note through the viewer strips the marker, so
from that save on the generator must leave the file alone.
`tests/test_foldernote.py` imports the generator and pins both halves.

### Geometry previews for STL, STEP, 3MF, and DWG

Version 0.6.0 fills in the previews Inventor never embedded. Roughly 250 files
in this workspace — 166 STL, 57 STEP/STP, 22 3MF, 6 DWG — showed the neutral
placeholder because only `.ipt`/`.iam`/`.idw`/`.ipn` carry a thumbnail.

`src/pihti_dedup/mesh_render.py` is a numpy software rasterizer: orthographic
isometric camera, z-buffer, flat shading from one key light plus ambient fill,
2× supersampled to 512 px, transparent background. Two facts from the spike are
load-bearing. Screen-bbox windows are bucketed **per axis**, not as a square
`max(w, h)`: render cost tracks screen-space triangle area rather than triangle
count, so the long thin slivers typical of low-poly CAD exports dominate, and
the per-axis fix took the worst case from 31.7 s to 2.1 s. And a conservative
centroid splat runs after the coverage pass, because a triangle thinner than a
pixel covers no pixel centre and would erase wire forms and sheet edges
entirely.

`src/pihti_dedup/dwg_preview.py` unpacks the preview AutoCAD already stored:
a 16-byte sentinel, a record table, and a BMP whose `BITMAPFILEHEADER` DWG
strips and this code synthesizes. Inversion keys on the image's **mean
luminance**, never the corner pixel — a paper-space preview is a white sheet on
a dark backdrop, and keying off the corner turns that sheet solid black. The
stored images are 180×180, so upscale is capped at 2.5× and the result is
centred on a card: grid-quality only.

`src/pihti_dedup/geometry_preview.py` is the front door and holds three
contracts. `render()` returns the existing `inventor_meta.Preview` and never
raises, so a corrupt mesh falls through to `placeholder_svg` exactly as a
missing Inventor thumbnail does. Optional dependencies are probed with
`find_spec` and imported only inside `render()`, so an install without the
extras degrades to placeholders instead of failing to import;
`available_extensions()` is the single truth about what an install can draw.
And rendering is disk-cached under the gitignored `.pihti-dedup/previews/`,
sharded two hex characters deep, written temp-then-replace, keyed by
`sha256(normcased path, mtime_ns, st_size, render size, RENDERER_VERSION)` —
the renderer version is in the key so a style change supersedes every stored
PNG rather than serving it stale. Only successes are stored: a negative entry
would outlive its reason, since installing the `step` extra does not invalidate
a "cannot be rendered" marker.

STEP costs seconds, so `pihti-dedup warm-previews` builds the whole workspace
once instead of letting a catalog visit trigger 250 renders. `/preview/...` is
the one route exempt from the blanket `Cache-Control: no-store`; it carries an
ETag over path, mtime, size, renderer version, and whether the response is a
real preview or the placeholder, plus `Last-Modified`, and answers a conditional
request with 304.

`cascadio` cannot open a non-ASCII path — OpenCascade's own IO limitation — so
`load_step` stages a non-ASCII source through an ASCII temp file first. The
tracked tree has no non-ASCII STEP today, but `staging/` holds ten and the
`ボディ*.ipt` set proves non-ASCII CAD names are normal here.

DXF stays uncovered. Unlike DWG it stores no raster to unpack, so it would need
a real 2D renderer rather than an extraction.

### Rendered Markdown view

Version 0.5.0 shows notes the way MkDocs and GitHub already show them.
`src/pihti_dedup/markdown_view.py` wraps `python-markdown` with `tables`,
`fenced_code`, and `sane_lists` — the same engine family as the documentation
site, so a table or a fenced block looks the same in both places. Sidecar prose,
the folder page's note, and an authored catalog note render by default; the raw
textarea and its unchanged token-protected Save move behind an "Edit raw text"
disclosure, so the file on disk is still what the owner types.

The renderer is narrowed twice, because it renders files that arrive through
student pull requests into a page carrying the viewer's form token. The
`html_block` preprocessor and the inline `html` pattern are deregistered, so raw
HTML is escaped to visible text rather than executed; HTML comments are removed
before rendering so a comment stays invisible instead of becoming literal text.
A treeprocessor strips `href`/`src` values whose scheme is not http, https,
mailto, or relative, which drops `javascript:` while keeping the link text.

Version 0.7.0 narrows the note contract with the rest of the page. Only the
current folder's authored note is present, folded behind a disclosure; a
generated index stays on the dedicated folder-note page because the adjacent
file view already expresses it. Immediate child cards may show their plain-text
excerpt, but no child note body or editor is loaded. Raw editing always takes a
deliberate trip to `/folder/<path>`.

Version 0.7.1 makes that rendered surface readable rather than treating prose
like secondary UI chrome: notes use a bounded measure, normal prose size,
visible heading hierarchy, and a contained background. The renderer still does
not invent structure for invalid Markdown. Instead, an empty editor provides a
valid heading/prose/fact-list example and the help text states the rules. The
existing `bellows/README.md` was normalized accordingly; its earlier consecutive
`label:value` lines were, correctly, one Markdown paragraph.

Version 0.7.2 fixes the producing system rather than one note. Every README that
still starts with `AUTOGEN_MARKER` is refreshed from the current template even
when its folder no longer meets the creation heuristic; marker-free authored
notes remain untouched. Generated pages contain actual inventory sections only,
not empty authoring placeholders. `--refresh-only` performs this migration
without creating files, and generator traversal now excludes staging, caches,
save history, and vendor `Design Data/` and `Templates/` subtrees.

Version 0.8.0 removes the three-click note path from Catalog. A single
folder-note row opens a native modal containing the rendered document and raw
editor together. The modal has explicit × and **Close** controls plus native
Escape and backdrop dismissal. Catalog-origin saves redirect to the same folder,
not the Catalog root, and the modal automatically reopens with success or
validation feedback. The dedicated `/folder/<path>` page is retained only as an
optional full-page view, with breadcrumbs and large rail actions back to the
current folder, its parent, and Catalog home. Folder-note guidance treats the
first prose line below `# Title` as a required one-sentence summary: the existing
folder cards render that excerpt while the full note holds detailed structure.
The Flask shell uses the same `pihtiicon.svg` bytes as MkDocs rather than a
separate generic favicon.

Version 0.9.0 makes metadata the narrative layer of Catalog cards. A file with
sidecar prose or an Inventor Description gets a two-column image-and-story card;
status, tags, material, and a nonredundant Part Number are compact chips. A file
with facts but no prose remains compact, avoiding the empty wide cards found in
visual QA. Sidecar prose wins over iProperties. Parsed Inventor metadata is
cached in memory against the inventory record's modification time and size, so
switching views does not reread unchanged documents. Folder-note excerpts are
multiline, prominent card content, and the root heading derives its purpose
summary from the repository `README.md` rather than hardcoded copy.

### Catalog folder rail

The 0.3.0 rail was a flat list of 99 folders that pushed the scan card off the
screen. The owner rejected an inner scrollbar as the fix, so 0.4.0 pinned the
scan card at the top and introduced the collapsible tree. Version 0.7.0 turns
that tree into route navigation: the current ancestry opens automatically,
unrelated branches collapse again on navigation, every folder count includes
its subtree, and the active leaf is marked. Depth is a CSS custom-property
indent, not a nested scrolling container. Until 0.15.0 a test asserted that no
rule imposed a height ceiling. On 2026-09-24 the owner reported that the rail
scrolled with the page when a large branch was open ("not nailed, hate it") and
ruled a pinned rail the priority. The rail now keeps its offset at every scroll
depth, and only the tree scrolls inside its capped card, which also scrolls the
current folder into view. The test now pins that ceiling and allows only that
inner scroll (see Status, 0.15.0).

### Decisions

The 0.1 first slice was report-only. Version 0.2 adds guarded merged-PR and
individually confirmed exact-byte quarantine operations. A later review sidecar may record a stable group
signature, disposition (`canonical`, `keep-both`, `needs-inventor`, `package-
baggage`), canonical path, reviewer, date, and note. Recording a decision must not
move CAD.

Before any broader web mutation ships:

- retain a CLI twin
- preview the complete operation
- verify Inventor references or record the verification gap
- move to recoverable quarantine rather than delete
- re-scan and open affected top-level assemblies in Inventor

## What cannot be inferred automatically

- Different hashes do not prove different geometry.
- Identical exported STL/STEP files do not prove their native Inventor sources
  are interchangeable.
- A filename match does not reveal which assembly currently references which
  path.
- Inventor resaves can change bytes without a meaningful design change.

Version 0.4.0's where-used index closes the fourth gap for `.iam`/`.idw`/`.ipn`
referrers, but it reads embedded strings rather than asking Inventor. It says
which documents *name* a file; it does not prove which one Inventor would bind
today, and a reference held only in a form this scan does not recognise would be
missed. Confirming it against Design Assistant on a sample remains open work.
Direct automation through Inventor APIs is optional later and must not block the
useful read-only viewer.

## Sources and precedents

- fleet `RULES.md` section 10: stationary navigation rail, shared grid, rail-card
  vocabulary, and Paperlib-before-new-UI rule.
- paperlib `src/paperlib/webapp.py` `_DUPLICATES` screen and `.folder-grid` /
  `.folder-panel` CSS: server-rendered shell, rail aligned at its sticky top from
  initial paint, async `/duplicates/results`, real filter buttons, and local
  read-only boundaries. Attendance-style dashboard headers are not a precedent
  for this viewer.
- lecturedeck `STYLE_GUIDE.md`: accents communicate semantic emphasis and are not
  decoration applied to every object.
- paperlib `src/paperlib/library.py`: signal grouping followed by stronger
  fingerprint classification.
- Autodesk Inventor Help, “To Work with Projects”:
  https://help.autodesk.com/cloudhelp/2025/ENU/Inventor-Help/files/GUID-34126F60-3093-4144-8AA5-809B4D35DCA1.htm
- Autodesk Inventor Help, “About Resolution of File Search”:
  https://help.autodesk.com/cloudhelp/2022/ENU/Inventor-Help/files/GUID-CD73F9CD-F485-4CAE-AA64-0E80BA15CCA3.htm
- Autodesk Inventor Help, “Pack and Go Reference”:
  https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Help/files/GUID-B25088E2-AF91-4774-A168-C141F6147AD8.htm
