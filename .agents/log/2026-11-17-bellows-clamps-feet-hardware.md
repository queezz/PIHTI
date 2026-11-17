# Clamps, feet, hardware and drawing fixes for the bellows set

- Goal: a run of queezz's requests while reviewing the renumbered shop set:
  - draw the flange clamps;
  - drop the middle foot's pocket;
  - take the clamp screws to M6;
  - name the screws by size, length and head;
  - add slack to the feet for rail spacing, with washers;
  - make the hardware list the complete buy list;
  - treat the clamp as an assembly, one part per page;
  - show sections instead of hidden holes;
  - start balloon leaders at the circle edge;
  - make the table plate's profile holes clear;
  - clock the lead-screw flat square to the view.
- Inventor work ran partly inside queezz's open session (main assembly and
  middle module visible). Their documents were never closed. Every edit was
  saved, and the session ended with zero documents open after they closed theirs.

## Model changes

- **Flange clamp.** `flange-camp-114.ipt` is one body of two lumps split by a
  5 mm gap. It stays as the master.
  - `flange-clamp-114-upper.ipt` and `-lower.ipt` derive the master and cut
    away the other side of y = 0. Their volumes, 130.34 + 167.11 cm³, sum to
    the master's 297.45 cm³.
  - `flange-clamp-114.iam` holds both halves, grounded.
  - It replaced the four clamp occurrences in the front (1), middle (2) and
    rear carriage (1) modules at the same transforms, named `Flange clamp n`.
- **Clamp threads and screws.** The clamp was already tapped M6 for the foot
  screws (thread 12 deep, drill 30) and M8 for the pinch screws, with Ø8.5
  clearance in the upper ear. Codex's model and list used M5 × 20 and M10 × 30.
  - New template copies, made by `SaveAs`, so the modules follow:
    - `fasteners/bellows-ISO-4762-M6x20.ipt`, cosmetic thread M6x1;
    - `fasteners/bellows-ISO-4762-M8x35.ipt`, from the content M10 × 30;
    - `fasteners/bellows-ISO-4762-M5x40-guide.ipt` for the guide screws.
  - Engagement:
    - M6 × 20 in the 6.5 counterbore: 11.5 mm.
    - M8 × 35 across the 14 mm ear and the 5 mm gap: 16 mm.
    - M5 × 40 with a 1 mm washer: 9 mm of the block's 12 mm through-tapped
      flange.
- **Feet** (`monotaro-front/middle/rear-flat-carriage-plate.ipt`):
  - The blank is 246 long instead of 238, grown symmetrically. The foot origins
    are unchanged to 0.001 mm.
  - The 8 guide holes are 5.5 × 8.5 slots along the foot, ±1.5 mm.
  - The clamp-screw holes are Ø6.6, with the CBORE Ø12 × 6.5 unchanged.
  - The middle foot lost "Radiused far support and clamp head pocket". Its
    second clamp pair now shows the same counterbores as the first.
- **Lead screw.** The journal flat sat on a fixed work plane at an arbitrary
  15.6° about the axis. That plane now faces +X: the same 5 mm from the axis,
  the same volume, healthy.
- **Screw names.** Codex's screw occurrences now say size, length and head:
  - `M5x40 cap screw - SBI block n`
  - `M6x16 low-head cap screw - rail n`
  - `M5x16 flat head screw - table n`
  - `M6x35 hex bolt - bypass branch n`
  - and the others in the same pattern.

  The bed and rear modules, the three carriages and the main assembly were
  renamed and saved.

## Drawing changes

- **17 and 18** are new sheets, one per clamp half. Each main view is section
  A-A at mid-thickness from the face or seat view, at 2 : 3:
  - outline, 60° sides, radii;
  - the bore as R57.25 with its centre 2.5 beyond the gap face;
  - hole notes and positions;
  - the note "MATES WITH No. 18/17 ACROSS A 5 GAP".

  Sourcing moved to 19.
- **01:**
  - lists and table rows for 17 and 18;
  - stacked 17/18 balloons on each carriage;
  - every balloon leader now starts at the circle edge, using 16 rim-insertion
    copies of `BP balloon`. A segment check finds no crossings and no leader
    through another balloon.
- **03:** hardware lines for M5 × 40 with washers, M6 × 20 and M8 × 35 with
  washers.
- **04:** the countersink callout is split into "12 × … TO AL PROFILES" (rows
  130 apart, columns 115 + 5 × 180) and "8 × … BACKING PLATES".
- **05–07:** slot callout, slot-end dimensions (53, 175, 40) on centrelines
  along each slot, the Ø6.6 clamp-hole notes, and 246 overall. On 06 the
  pocket dimensions are gone and the note reads "4 × Ø6.6 THRU CBORE Ø12 ×
  6.5 DEEP".
- **12:** the flat now reads edge-on at the top of the main view and level in
  A-A, where "11" was re-attached.
- **Thin isometric edges** reapplied on 01–03.

## Hardware list

- `monotaro-basket.md` "Hardware to buy" lists:
  - M5 × 40 (26), M5 washers (24);
  - M6 × 20 (8), M8 × 35 (8) with M8 washers;
  - M4 × 12 (4);
  - a vacuum table: 24 M8 × 45 bolts and nuts, M6 × 35 (16), M6 × 25 (6),
    M6 nuts (16).
- The clamps are no longer "existing, reused".
- `sourcing/monotaro-drive-and-wheel.md` matches.
- MonotaRO order codes for the new sizes were not looked up.

## Verification

- Every edited sheet passes the overlap check. Rendered:
  - 01, 03, 04, 05, 06, 07, 12, 17, 18, 19;
  - the whole set at low resolution.
- After updating and saving the bed and main assemblies, the IDW reopens with
  no missing references; 135 dimensions and 68 centerlines are attached, and
  it is clean.
- Shop PDF thinned with `pdf-strokes --pages 4-19` (131 widths). Its text is
  identical to the raw export, with no "BP-MON".
- Failures on the way, now in the how-to:
  - A changed view camera dragged sections and dimensions; undone with
    `UndoTransaction`.
  - New symbol definitions refused leaders.
  - Sheet names with commas were ignored.

## Not committed, for queezz

- `monotaro-bed-module.iam` and `sliding-assembly-monotaro.iam` carry queezz's
  earlier uncommitted edits plus this session's renames and update saves.
- `flange-camp-114.ipt` shows modified. This session did not edit it; it may be
  queezz's save while it was open.

## Open

- Washers are on the list and the assembly page but are not modelled.
- MonotaRO codes for M5 × 40, M6 × 20, M8 × 35, the washers and the vacuum
  bolts.
- Earlier owner decisions stand: material grades, fits, and the rail-pitch
  tolerance, now eased by the slots.

## Follow-up: the drive nut's mounting

queezz asked whether the nut that drives the stage hangs on 2 M5 screws. It
does:

- **Load path:** screw → TR16 nut (No. 11) → keeper (No. 14, 4 × M4) →
  saddle (No. 10) → 2 × M5 → rear foot (No. 07).
- **Load:** the vacuum force, estimated at 0.4–0.5 kN from the flange bore
  Ø63.5 and the Ø83 counterbore. It always pulls the rear carriage toward the
  middle.
- **Capacity:** friction, at about 4 kN preload per screw, holds about
  1.6 kN, roughly 3–4× the load. Prying adds about 0.25 kN, because the saddle
  pivots about the edge 25.5 mm from the screws.
- **Weak spot:** the M5s engaged only 6.5 mm (1.3D) in the aluminium foot.

Applied, as recommended:

- `monotaro-rear-flat-carriage-plate.ipt`: the saddle pilots ("Saddle M5 tap
  pilots through") now run through all 15 mm.
- `fasteners/bellows-ISO-4762-M5x45.ipt`, from the M5 × 40 template by
  `SaveAs`, which only the saddle used. The two saddle screws are
  `M5x45 cap screw - nut saddle n` and engage 11.5 mm; their tips stop 3.5 mm
  below the foot top.
- Sheet 07 now reads "2 × M5 × 0.8 THRU, FOR THE NUT SADDLE (No. 10)".
  Sheet 03 reads "2 × M5 × 45 saddle".
- The basket splits M5 × 40 (24, guide) from M5 × 45 (2, saddle). The drive
  sourcing table matches.
- The bed and main assemblies were updated and saved. The IDW reopens clean:
  no missing references, all dimensions and centerlines attached. Shop PDF
  re-exported and thinned (`--pages 4-19`); text identical.

## Follow-up: who assembles

queezz clarified that 工作室 makes the parts and may test-fit them, but does
not assemble; Kuzmin assembles in another building. The set was reworded:

- **03:** the subline reads "Kuzmin assembles; 工作室 makes the parts and may
  test-fit them", replacing Codex's "REV C / … / Machining review". The wheel
  block is split into `工作室:` machining (drill, tap, deburr the ASH125 boss)
  and `Kuzmin:` fitting (align to the flat, set screw, collar, endplay).
- **01:** "Kuzmin assembles the stage. No. 03 has the assembly sequence …".
- **02:** the "REV B" leftover is dropped.
- **16:** "KUZMIN FITS AN M5 × 10 … AT ASSEMBLY (No. 03)" replaces "FIT M5 ×
  10 …".
- **19:** "工作室 may test-fit the bearings, nut and wheel in their seats;
  Kuzmin assembles" replaces "Match the bearing seats …".
- The how-to house style records the split.
- The IDW reopens clean; the shop PDF is re-exported, thinned and installed.

## How-to update

queezz asked for the how-to to be updated. Added, with evidence from this log:

- A **Part edits through COM** section covering:
  - dimension-free sketch edits, holes to slots, through extents and feature
    deletion;
  - re-clocking a fixed work plane;
  - splitting a multi-lump part into derived pieces and an assembly.
- A **Working inside the owner's open session** section covering stale
  parents, modal notices and finding dialogs with UI Automation.
- Fastener size changes through `SaveAs`, thread reset and occurrence naming.
- Fit rows for the guide, clamp and saddle screws, plus an engagement and
  vacuum-load rule of thumb.
- Drawing notes: `Precision`, which side leader-note text lands on, full
  diameter lines, slot dimensions.
- Verification that tolerates documents the owner already has open.
