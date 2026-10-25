# Modular sensor box

Removable-panel development for a humidity sensor box and an ADC box with a divider, retaining the current enclosure size.

## Scope

Queezz wants two instruments using the current box dimensions, with small
changes to the module holding board. Front and rear panels must be replaceable
without loosening the electronics sandwich. The extra 5 mm at the front is
intentional wire space and must remain (owner, 2026-10-26).

One, two or three interaction buttons may later control the screen or change
pages. Button selection, openings and printed covers are deferred. These panel
blanks also defer display and connector openings until the two instrument
layouts are settled. They are not replacements for the existing logger's
populated panels.

## Prototype mounting design

- Each panel is a separate, editable Inventor part: 74 x 60 mm, 3 mm thick,
  with 5 mm corner radii and a 0.5 mm outer-face perimeter chamfer.
- Four inward returns attach each panel with side-access M3 screws. No panel
  fixing passes through the front or rear face. The sleeve covers the screw
  heads when installed.
- New upper and lower mount spacers retain the sandwich rod bores and add
  inward mounting wings. The spacers include the clamped thickness formerly
  supplied by the captured panel ears. Removing a panel therefore does not
  release the sandwich.
- The upper spacer is 17.49 mm long and the lower spacer is 24 mm long in the
  measured fit fixture. The original short spacers, shelf and outer sandwich
  plates remain shared.
- Panel screw axes are at x = +/-33.3 mm, y = +/-32 mm, z = +/-20 mm in the
  fit assembly. Screws enter from the sides. The insert seats are offset
  6.5 mm from the sandwich rod axes, keeping their bores separate.
- Hardware is referenced directly from `ContentCenter/Fastners`: eight
  `M3x8-BHCS.ipt` screws and eight `brass-insert-m3x5.ipt` inserts.
- Insert pilots are a prototype 4.6 mm diameter with 5 mm collar seats.
  Validate the pilot with the actual inserts and printing process before
  printing a complete set. Insert interference in CAD is intentional.

The front inner face remains at y = 50 mm; the rear inner face is at
y = -45 mm. The shelf ends at y = 45 mm, preserving the 5 mm front wire gap.
Front returns reach 21 mm inward; rear returns reach 16 mm inward. The
mounting interface is common despite that difference.

## Files and reuse

| File | Role |
| --- | --- |
| `sensor-box-front-panel.ipt` | Front blank with longer mounting returns |
| `sensor-box-back-panel.ipt` | Rear blank |
| `sensor-box-upper-mount-spacer.ipt` | Upper rod spacer and panel receiver; four instances |
| `sensor-box-lower-mount-spacer.ipt` | Lower rod spacer and panel receiver; four instances |
| `SensorBox-panel-fit.iam` | Mechanical inspection fixture using shared existing parts |

The fit fixture references unchanged enclosure and frame parts from
`../esp32-ambient-logger/`; it does not copy them into this folder. The existing
PCB (`TempLoggerRev1.iam`), ESP32, SD reader and RTC are also shared references,
retaining their existing positions (owner, 2026-10-26). The thermocouple plug,
thermocouple converter and DC jack are not brought into the new fixture. Its
components are deliberately grounded at measured positions for inspection.
It is not a constrained instrument assembly or a finished humidity/ADC design.
Panel faces are blank. The humidity sensor needs exposure to outside air,
because conditions inside the enclosure differ; no extra space is required on
the red mounting plate (owner, 2026-10-26). Its specific mounting and wiring,
the ADC/divider board and instrument-specific cutouts remain to be designed.

Dimensions and feature sketches are native Inventor features. Panel width,
height, face thickness and screw clearance have named parameters. Mount
spacer length, rod clearance and insert diameters also have named parameters.
The return profiles and offsets remain separately editable; changing the
box envelope requires reviewing those sketches and the fit assembly too.

## Servicing

1. Slide off the enclosure sleeve.
2. Disconnect the selected panel's wiring as needed.
3. Remove that panel's four side screws.
4. Pull the panel straight outward, leaving the sandwich rod nuts tightened.

The sleeve must be removed for screw access. A change from the logger's old
captured ears to these mount spacers requires an initial sandwich rebuild;
subsequent panel changes do not.

## Verification

Native checks and dimensions are recorded in `fit-check.json`.

- All new part features are healthy; the saved fit assembly reopens with
  resolved references. Original logger CAD files remain unchanged.
- Panel withdrawal was checked at eight positions from 0 to 30 mm outward
  for each panel, with panel screws removed and the sandwich left fixed.
- The new mounts clear the existing internal boards. The unchanged sleeve
  clears the assembled frame, panels, hardware and retained electronics at
  a measured sleeve centre of y = 2.8 mm.
- Intentional insert/pilot interference and existing simplified nut/rod
  overlap are distinguished from component collisions.
- Physical printing, insert installation, wiring clearance and tool use
  have not yet been verified on hardware.

![Panel mounting fit fixture](panel-fit.png)

![Panel mounts and shared electronics](panel-mount-detail.png)
