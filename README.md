# PIHTI — Inventor Workspace

Autodesk Inventor project archive for experimental plasma, vacuum, and spectroscopy hardware.
Covers mechanical design from first concept through fabrication drawings.

**📖 Documentation:** [queezz.github.io/PIHTI](https://queezz.github.io/PIHTI/)

**Agent cold start:** [`README_SHORT.md`](README_SHORT.md)

The project file is `PIHTI.ipj`.

---

## What is in here

### Plasma systems

`Plasma Vessel/` — the main plasma chamber assembly. Includes the vacuum cross
(`Plasma-vacuum-vessel-152IC-cross`), the plasma box (`Plasma-box-hayashi-aka-upgrade`),
cathode/anode flanges with water and electrical feeds, and a 2024 flange revision.
The `CathodeCage` and `Cathode-Flange-Cage` sub-assemblies document the cathode
support structure.

`PLD/` — FDM printed pulsed laser deposition test chamber. Octagonal body (`pld-octogon`), nipples,
viewport flanges (AKF-100, AKF-60/NW-25), target holder, sample holder, and o-ring
seals. Includes test geometries for overhang/cone printability checks.

`TMP-PT-50/` — adapter hardware between a turbomolecular pump (VF65 port) and
ICF-114 flanges.

### Probes and diagnostics

`BoronProbe/` — insertable boron probe. Multiple head variants (`BoronHead`,
`BoronProbeHead`), pipe assemblies, and a hybrid configuration for PALP
(`palp-boron-hybrid`).

`PALP/` — probe assembly. Prototype (`PALP-prototype`), ICF-34 nipples, and
a KF o-ring seal variant. Shares geometry with `BoronProbe`.

`LIBS/` — mechanical parts for a Laser-Induced Breakdown Spectroscopy setup.
Includes an XL430 servo bracket for positioning (`XL430_W250_T`, `XL430-bracket`)
and a TAS-20605L sensor mount.

### Spectroscopy and optics

`Jobin-Yvon/` — camera and lens adapters for the Jobin-Yvon 650mm spectrometer. Mounts for
QHY183, RisingCam (IMX571), and Takumar lenses. Includes a collimator attachment
for the Fujii echelle configuration and a slit assembly with LED.

### Electronics enclosures

`ElectronicsBox/` — DIN-rail and bench enclosures for various lab instruments:

| Subfolder | Contents |
|-----------|----------|
| `BaratronBox/` | enclosure for a Baratron capacitance manometer |
| `TempController/`, `TempController-v2/` | thermocouple-based temperature controller boxes, two generations |
| `ThArLamp/` | enclosure for a Th-Ar hollow cathode lamp |
| `PL08/` | enclosure variant (`ThArLampEnclosure`) |
| `esp32-ambient-logger/` | ESP32-based temperature/ambient data logger, multiple PCB and enclosure revisions |
| `LP-box/` | Langmuir Probe divider enclosure |
| `Win-GPIO-Box/` | GPIO breakout box for Windows-based control |
| `slidebox-teplate/` | parametric DIN-rail slide box template |

### Support and fixtures

`SampleHolder/` — snap-fit sample holder box (`Box-with-snaps`).

`Scaffolding/` — support stand for the plasma flange (`Plasma-flange-on-support`).

`Desks/` — welding desk design.

### Shared component library

`ContentCenter/` — reusable Inventor components: aluminium profiles, CF/KF vacuum
fittings, JIS flanges, NW fittings, connectors, optics, and third-party modules.
These are referenced by assemblies throughout the workspace. See
[ContentCenter/README.md](ContentCenter/README.md) for a category listing.

---

## Repository structure

The folder layout reflects the evolution of the lab over time and has not been
reorganised. Sub-assemblies live alongside their parent assembly rather than in a
dedicated library hierarchy. Some folders contain multiple design generations or
abandoned variants — these are kept as-is for reference.

`OldVersions/` subdirectories appear throughout. They contain superseded file
revisions saved by Inventor and are excluded from version control (see `.gitignore`).

---

## Navigation

[`INDEX.md`](INDEX.md) lists every folder that contains assemblies and identifies
the primary `.iam` in each. It is auto-generated and reflects the current state of
the tree.

Most assembly folders also contain a `README.md` with the current main assembly,
assembly list, and part list. These generated inventories are navigational
scaffolding, not a substitute for reading the actual Inventor files or drawings.
Editing one by hand or through the viewer removes its generator marker and claims
it as authored documentation.

To regenerate after adding new folders:

```
python scripts/generate_readmes.py
```

The script refreshes files that still carry its marker and never rewrites a
marker-free authored `README.md`. Run with `--dry-run` to preview the complete
plan. Use `--refresh-only` to update existing generated files without creating
new `README.md` or `INDEX.md` files. Staging, save history, caches, and vendor
`Design Data/` and `Templates/` trees are outside its scope.

### Duplicate review

The local duplicate viewer finds repeated CAD filenames across the Inventor
workspace, then uses SHA-256 to distinguish byte-identical copies from files
whose contents conflict. Scanning is read-only. Explicit cleanup actions move
validated byte-identical files to recoverable quarantine; the tool never chooses
a canonical part or rewrites assembly references.

From the repository root, install it into the external environment and scan:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pip install -e ".[dev,preview,step]"
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup scan .
```

The `preview` and `step` extras are optional. They add previews for CAD files
that carry no embedded thumbnail; without them those files simply show the
neutral placeholder.

Start the viewer through the fleet launcher:

```powershell
lab pihti
```

It opens `http://127.0.0.1:4185/catalog`. The direct module command remains
available for development, but `lab pihti` is the normal operating surface.

Catalog is the landing view; open **Duplicates** in the top navigation when the
filename-collision inventory needs review. The server builds an in-memory
snapshot from the metadata-validated inventory under gitignored
`.pihti-dedup/` and serves every page from it, refreshing that snapshot in the
background every few seconds while the viewer is in use (about once a minute
when idle) and rehashing only paths whose size or modification time changed.
**Refresh** on Duplicates remains the explicit full verification, and every
mutation still revalidates the live disk before acting. `lab pihti` is the
normal way to start the viewer; the direct command form takes a
`--refresh-seconds` flag to change that period, and `0` restores the previous
validate-on-every-request behaviour:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup serve . --refresh-seconds 0
```

In Duplicates, use the two right rails to review one duplicate kind, project
folder, or recent merged PR at a time. PR filters come from local first-parent
Git history and do not require GitHub access. Each member row can copy either the
absolute file path for Inventor's **File name** field or its containing folder for
the dialog's address bar. Rows include size,
modified time, and the short byte hash.

Byte-identical rows also have a **Delete** action. Its confirmation revalidates
the selected file's path, size, modified time, and SHA-256, requires another
identical survivor, then moves only that member to gitignored quarantine and
writes a restoration manifest. `*.newVer.ipt` pairs are called out separately:
the current workspace has seven base/`newVer` pairs with identical bytes and
timestamps, but that evidence does not prove which program created the suffix.
The complete review context—text, kind, folder, merged PR, extension,
cross-folder scope, and vendor scope—survives deletion, rescans, and reloads.
After a mutation, the refreshed list keeps the next visible group at the same
viewport position and reports success in a fixed toast instead of inserting a
banner that shifts the results.

Different-byte collision rows support owner-reviewed cleanup after the revisions
have been opened and compared in Inventor. **Quarantine this** moves only the
selected revision; **Keep only this** selects a canonical survivor and moves
every other member. Either action also moves an adjacent metadata sidecar to the
sibling `PIHTI-quarantine/runs/` store. The searchable
**Removed** page records each old path, the chosen survivor, possible referrers
by filename, and a guarded Restore action. Opening an old part URL returns the
same answer instead of a generic 404. Files beneath a top-level folder introduced
by a merged PR carry an orange PR-folder badge. A file added elsewhere by a PR
is also orange; a pre-existing file merely edited by a PR instead carries a
neutral **Edited PR** history badge and is not marked as a deletion target.
The Removed view groups same-kind actions made within ten minutes into compact,
collapsible sessions. Its rail filters recoverable/restored history and expands
or collapses visible sessions; restoration remains scoped to one exact event.

Use **Doctor** when the right operation is renaming rather than consolidation.
Assembly Workbenches are the primary route for STEP/import repair: choose the
referring `.iam`, inspect its preview and direct embedded names, then keep that
assembly as the context while repairing one component at a time. Missing names
remain visible until Inventor repoints and saves the assembly. For each missing
name, Doctor searches every reachable Git ref and shows whether the file was
never tracked, was deleted, or was renamed; historical Inventor previews and
copy-ready current rename destinations sit beside that evidence.
Collision Doctor opens every repeated Inventor filename as one durable repair
session, so renaming two members cannot make the final unversioned member vanish
from Duplicates. Name Doctor also finds low-information imported names such as
`Body.ipt`, `Body001.ipt`, and `Part.ipt`, including singletons. A name session
keeps current originals, already-renamed destinations, and every filename-based
referring assembly together, with copy-ready file and folder paths for Inventor.
The Renames page recalculates **Inventor will ask now** from the live workspace;
the ledger still notes when the outcome differed at rename time.

Doctor's **Standard parts** card lists fasteners that sit outside
`ContentCenter\Fastners`. A part is listed when its `standard` iProperty is set,
its filename carries a JIS, ISO, DIN, or ANSI designation, its name follows the
library convention (`M3x10-SHCS.ipt`, `M3-nut.ipt`, `M4-Washer.ipt`), or its
description names a fastener. Each row shows that evidence. A uniquely named
part gets a **Move** button: the part and its sidecar move into the library,
and the move is recorded in the rename ledger. Referring assemblies still find
the part, because Inventor resolves by filename. A byte-identical copy already
in the library gets **Quarantine copy** instead. A name that exists elsewhere
is refused and links to Collision Doctor. Every row is confirmed on its own,
and **Skip** hides a row for this browser tab only. The CLI twin is
`pihti-dedup standard-parts . --dry`; `--apply --references-checked` runs only
the plain moves.

### Previews

Inventor documents and DWG drawings show the preview image they already embed.
STL, STEP/STP, and 3MF carry none, so the tool renders one from the geometry and
caches the PNG under gitignored `.pihti-dedup/previews/`. A STEP render costs a
second or two, so build them all once instead of paying for them on a catalog
visit:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup warm-previews .
```

The cache is keyed by the file's modification time and size, so a resaved part
is redrawn automatically and nothing has to be cleared by hand. DXF is not
covered and shows the placeholder.

For a merged PR, preview merge-added same-name, byte-identical copies from the
viewer or CLI:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup merge-cleanup . --pr 3 --dry
```

After checking the affected references in Inventor or Design Assistant, apply
the same plan with:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup merge-cleanup . --pr 3 --apply --references-checked
```

Apply mode never permanently deletes files. It revalidates path, size, modified
time, and SHA-256; keeps
at least one identical copy outside the merge, moves only merge-added candidates
to gitignored `.pihti-dedup/quarantine/`, writes a restoration manifest, and
rescans. Modified pre-existing files and groups introduced entirely by the same
merge are protected.

Pack-and-Go support files under `bellows/Design Data/` and
`bellows/Templates/` are excluded by default and can be included from the
viewer. The original `scripts/find_duplicates.py` command remains available for
the earlier JSON/CSV/Markdown inventory workflow.

### Part catalog and metadata sidecars

The same local server serves a hierarchical catalog at `/catalog`, folder routes
below it such as `/catalog/Plasma%20Vessel`, and `/part/<path>` for one file.
Catalog and part pages share one three-column layout: a wide left rail with the
current folder or file, the thumbnails in the middle, and the folder tree on the
right, with the current branch open. Both rails stay in place while the page
scrolls; a long tree scrolls inside its own card. A single line above the
thumbnails holds the breadcrumb and a filter field. Typing filters the folder
cards and file tiles already on the page; Enter, or **Search whole archive**,
runs the global server-side search instead. Large file sets and search results
appear 48 at a time behind an explicit **Show 48 more** control.

The thumbnails come first. Child folders are cards with a strip of up to six
previews from the files below them (Inventor documents first); the folder's own
files follow in a separate grid. At the workspace root the `PIHTI.ipj` project
file stands in the left rail with a copy-path button rather than as a tile.
Hovering a file tile, or moving to it with the arrow keys, shows it in the left
rail's inspector: the preview at its own pixel size, plus description, part
number, material, valid mass, modification date, and the documents that use it,
when those exist. Enter opens the part page; Escape clears the inspector.

Badges on file tiles flag what the inventory already knows, each a short word
in a small coloured box in a row under the tile's size line: `clash` (same
name, different bytes), `copy` (an identical copy elsewhere), `renamed` (same
bytes under another name), `unhashed` (same name, bytes not compared yet),
`generic` (a generic name), `newer` (a newer file with this name exists), `main`
(a main assembly), and `featured`. Hovering a badge shows its full meaning.
The inspector and the part page's File card list the same badges with that
meaning beside each, and the **Legend** at the bottom of the left rail always
shows all eight, in the same order, on every catalog and part page.

The folder note shows in the left rail as rendered Markdown. Only the part
you wrote is shown, not the generated inventory lists, and it sits in the same
fixed space on every folder. A longer note fades out. **Read the whole note**
opens the note in a reader, and **Edit** beside the × switches to the raw
editor with a live preview. Save returns to the same folder and reopens the
reader with feedback. Close it with ×, **Close**, Escape, or the backdrop. A
folder without a note shows **Write one**, which opens the editor directly.
The optional full-page editor has breadcrumb navigation and prominent rail
cards back to the current folder, its parent, and the Catalog root.

Mark a folder's main assembly with **Make main assembly** in the inspector or
**Main assembly** on the part page. One
click writes `hero: true` into the file's metadata sidecar and creates the
sidecar from iProperties if needed; clearing it asks first and removes that one
line again. A folder can have several heroes, and any CAD file can be one.
Heroes lead their folder as a **Main assemblies** row of ordinary tiles and are
not repeated among the files below. The catalog root lists every hero in the
archive with its folder as the click target, and folder cards show their
heroes first in the preview strip. A gold dot in the tile corner marks a hero;
the inspector states it as a fact, and its toggles name the file they act on.
**Feature on folder card**, beside it in both places, writes `featured: true`
instead: the file then leads the preview strip of every folder card above it
without joining the Main assemblies row. When nothing is marked, a folder card
samples one representative per subfolder, preferring an assembly that nothing
else references, then any assembly, then a part.

For useful browse cards, put a one-sentence folder summary directly below the
note's `# Title`. The Catalog extracts that first prose line and shows it on the
folder card; subsequent headings and labelled facts stay in the full note. The
editor prompt and empty-note template make this structure explicit.

Catalog file tiles use the same principle. When a metadata sidecar contains
prose, or an Inventor document carries a useful Description, the tile becomes a
wider image-and-story card. Status, tags, material, and a nonredundant Part
Number appear as readable chips; material-only records stay compact. Sidecar
prose takes precedence over iProperties, and iProperties reads are cached until
the CAD file's size or modification time changes. The Catalog root's left rail
also shows the repository README's opening summary.

The layout targets a desktop window from about 1400 to 2560 pixels wide, beside
Inventor. Below 1200 pixels both rails move into one right-hand column and the
inspector is omitted; phone and laptop layouts are not designed.

Thumbnails use the preview image Inventor already embedded or the cached
geometry render described below; files without either show a neutral
placeholder. Duplicate rows carry the same thumbnail, so same-name collisions
can be triaged visually before opening Inventor.

A part page reads iProperties straight out of the file: part number,
description, material, designer, author, creation date, document subtype, and
the Inventor build that last saved it. Mass, volume, density, and surface area
appear only when Inventor's own `Valid MassProps` flag says its cached values
are still good. When the Part Number differs from the filename, the page says so
prominently — Inventor resolves references by filename, so the two records
disagreeing is worth seeing.

Free-form notes live in a **metadata sidecar**: a Markdown file named after the
whole CAD filename, so `B_probe_bearing.ipt` gets `B_probe_bearing.ipt.md` next
to it. It holds YAML frontmatter (`part_number`, `material`, `status`, `tags`,
`supersedes`, `seeded_from_iproperties`, `hero`, `featured`) followed by free prose. The part page
creates one seeded from iProperties, or edits the raw file in a textarea; the
server refuses to write frontmatter it cannot parse. Sidecars are never
committed for you — they appear as untracked or modified files in your own Git
flow.

To seed the whole workspace at once, preview first:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup meta seed . --dry
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup meta seed . --apply
```

`--dry` prints counts and a sample and writes nothing. `--apply` writes sidecars
only for `.ipt`, `.iam`, `.idw`, and `.ipn` files that do not have one yet;
existing sidecars are never overwritten.

---

## Local documentation environment

The repository uses [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)
to render all `README.md` files as a browsable site. A dedicated venv is the
simplest setup — no Conda required.

```powershell
python -m venv $HOME\.venvs\mkdocs
& "$HOME\.venvs\mkdocs\Scripts\Activate.ps1"
pip install mkdocs-material mkdocs-glightbox
```

Activate that environment in any later session with:

```powershell
& "$HOME\.venvs\mkdocs\Scripts\Activate.ps1"
```

**Serve locally** (live-reloading, available at `http://127.0.0.1:8000`):

```powershell
mkdocs serve
```

**Build and validate** (fails on broken nav links, use before pushing):

```powershell
mkdocs build --strict
```

GitHub Actions builds and deploys the site automatically on every push to `main`.
See `.github/workflows/gh-pages.yml`.

---

## Notes for collaborators and students

- Open `PIHTI.ipj` in Inventor before opening any `.iam` or `.ipt` files. The project
  file sets the library search paths; without it Inventor will fail to resolve
  `ContentCenter` references.
- Do not rename or move `.iam`/`.ipt` files outside of Inventor. Assembly references
  are stored as relative paths inside the files themselves.
- Drawing files (`.idw`) and PDFs live in `Drawings-PDFs/` and are not indexed here.
- `LaserCutting/` and `3D-printing/` contain output geometry (DXF, STL, 3MF) derived
  from parts in the main tree. They are not Inventor assemblies.
- If a component looks incomplete or wrong, check for a newer version in a sibling
  folder before assuming the design was abandoned.
