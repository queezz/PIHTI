# Create removable panels for two sensor boxes

## Goal

Create a new folder with independently removable front/rear panels for a humidity
sensor box and an ADC/divider box, sharing unchanged CAD rather than copying it.

## Decisions

- Owner retains the current enclosure dimensions. The 5 mm front offset is
  intentional wire space, not an error to eliminate.
- Owner retains the PCB, ESP32, SD reader and RTC. The humidity sensor needs
  outside exposure; no additional red mounting plate area is required.
- No thermocouple plug, converter or DC jack was included. Display, connector,
  ADC/divider and one-to-three-button details remain future instrument work.
- New panels use four side-access M3 screws each, concealed by the sleeve.
  Their inward returns attach to wings on two new spacer variants. The spacers
  replace the old ear thickness in the rod stack, so panel removal does not
  loosen the sandwich. An initial spacer conversion does require rebuilding it.
- Upper spacers are 17.49 mm; lower spacers are 24 mm. The insert bores are
  offset from the rod bores. M3x8 button screws and M3x5 inserts are existing
  shared ContentCenter parts. The 4.6 mm insert pilot remains a print-fit trial.
- One common mechanical fit fixture, with grounded components, is supplied;
  it is not represented as two finished or constrained instrument assemblies.

## Changed

- ElectronicsBox/modular-sensor-box/: two native panel blanks, two native mount
  spacer parts, SensorBox-panel-fit.iam, README, two native-view PNGs, and
  fit-check.json. Unchanged parts and electronics remain shared references.
- .agents/CHANGELOG.md: record the new CAD prototype milestone.
- This handoff. No runtime software or existing CAD was edited.

## Verification

- Read-only duplicate scan before creation: 1,216 CAD files, 19 same-filename
  groups, 12 different-byte name collisions, 7 exact-copy filename groups,
  and 14 different-name exact-copy groups. No cleanup was performed.
- Native assembly: 50 occurrences; reopened with all 140 referenced files
  resolved. All features of the four new parts report healthy status 11778.
- All 320 original native files beneath the logger folder retain their SHA-256
  hashes. The open source assembly's pre-existing dirty state and relationship
  health were preserved; it was never saved by this work.
- Existing PCB/ESP32/SD/RTC references and transforms match the source.
- Native panel withdrawal checks at 0, 0.5, 2, 5, 10, 15, 22 and 30 mm: no
  panel collisions with screws removed, frame and electronics fixed.
- New mounts clear the existing board context. Native sleeve fit is clear at
  y = 2.8 mm centre with the original cross-section and length. A first centred
  trial caught the front end lip; the measured seating and new panel edge
  chamfers were verified before accepting the fit.
- Heat-set insert/pilot overlap is intentional and requires physical testing.
  Existing simplified M3 nut/rod overlaps remain; no other fit collisions.
- Saved native overview/detail images were visually inspected.
- Ruff passed; 525 pytest tests passed in 53.11 s using a fresh owner-context
  machine-local basetemp. The initial sandbox run failed to create temporary
  directories; it did not reveal source/test failures.
- MkDocs strict build passed with output outside Dropbox. git diff --check
  passed. notes check reports only two pre-existing missing summary sentences
  in BoronProbe_2026/README.md and Plasma Vessel_2026/README.md; the new folder
  note has no finding.
- Source evidence scripts and temporary MkDocs output were kept outside Dropbox
  in this chat's visualization scratch directory. Existing unrelated dirty CAD
  and image/sidecar files were left unstaged.

## Next

Print a small mount/insert fit sample before making a full set. Develop separate
humidity and ADC/divider cutout layouts from the common panel interface, choose
screen and button hardware, and route the externally exposed humidity sensor.
Preserve the front wire space while doing so.
