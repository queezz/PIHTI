# Modular sensor box

Removable-panel development for a humidity sensor box and an ADC box with a divider, retaining the current enclosure size.

## Scope

Queezz wants two instruments using the current box dimensions, with small
changes to the module holding board. Front and rear panels must be replaceable
without loosening the electronics sandwich. The extra 5 mm at the front is
intentional wire space and must remain (owner, 2026-10-26).

One, two or three interaction buttons may later control the screen or change
pages. Button selection, button openings and printed covers are deferred.
The front now carries the existing OLED and its mount. Rear openings provide
ESP32 USB and micro-SD card access. Other instrument connectors remain to be
laid out; the panels are not a complete replacement for the old logger's
thermocouple/power connector arrangement.

## Prototype mounting design

- Each panel is a separate, editable Inventor part: 74 x 60 mm, 3 mm thick,
  with 5 mm corner radii and a 0.5 mm outer-face perimeter chamfer.
- Four inward returns attach each panel with side-access M3 screws. No panel
  fixing passes through the front or rear face. The sleeve covers the screw
  heads when installed.
- New upper and lower mount spacers are plain 7 x 13 mm rectangular blocks,
  each with one rod bore and one straight transverse insert bore. There are
  no steps, collar recesses, chamfers or fillets on these spacers. Queezz will
  add edge treatment for printing and strength (owner, 2026-10-26).
  The spacers include the clamped thickness formerly
  supplied by the captured panel ears. Removing a panel therefore does not
  release the sandwich.
- The upper spacer is 17.49 mm long and the lower spacer is 24 mm long in the
  measured fit fixture. The original short spacers, shelf and outer sandwich
  plates remain shared.
- Panel screw axes are at x = +/-33.3 mm, z = +/-20 mm, with y = 45 mm at
  the front and -32 mm at the rear. Front blocks face outward into the corner
  wire-gap space so the front returns can be shorter; rear blocks face inward.
  Both ends reuse the same upper/lower parts. Insert axes are offset 6.5 mm
  from the sandwich rod axes, keeping their bores separate.
- Hardware is referenced directly from `ContentCenter/Fastners`: eight
  `M3x8-BHCS.ipt` screws and eight `brass-insert-m3x5.ipt` inserts.
- Insert pilots are plain, prototype 4.6 mm through bores.
  Validate the pilot with the actual inserts and printing process before
  printing a complete set. Insert interference in CAD is intentional.

The front inner face remains at y = 50 mm; the rear inner face is at
y = -45 mm. The shelf ends at y = 45 mm, preserving the 5 mm front wire gap.
Front returns reach 8 mm inward; rear returns reach 16 mm inward. Return
thickness is 3.3 mm so the inner faces meet the plain 7 mm spacer faces while
the outer screw seating faces stay in place. The middle of the front wire
gap remains clear.

## Display and rear access

- The existing OLED, screen mount and four M2 screws are shared references
  in their original positions. The front preserves the proven snug seat:
  30 x 30 mm opening, 2 mm corner radii and 0.5 mm entry chamfers, matching
  the original panel. No OLED or mount geometry was changed. Do not enlarge
  this opening for clearance (owner, 2026-10-26).
- The rear USB opening is 14 x 7 mm, centred at assembly x = 0.72 mm,
  z = 20.16 mm, aligned with the measured ESP32 USB-C connector.
- The rear SD removal opening is 20 x 10 mm, centred at x = -11.25 mm,
  z = -5.5 mm. The modeled card clears it through a 20 mm withdrawal,
  ending fully outside the rear panel.
- Rear openings are square-edged. Physical access with the selected USB cable,
  finger access and printing tolerances still need hardware checks.

## Files and reuse

| File | Role |
| --- | --- |
| `sensor-box-front-panel.ipt` | OLED opening and short mounting returns |
| `sensor-box-back-panel.ipt` | USB and SD access openings |
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
The humidity sensor needs exposure to outside air,
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
- Revised panel withdrawal was checked at 0, 2, 10 and 30 mm outward, with
  panel screws removed and the sandwich left fixed. The OLED, mount and M2
  screws travel together with the front panel in this check.
- SD withdrawal was checked at 0, 5, 10 and 20 mm through the rear opening.
- The new mounts clear the existing internal boards. The unchanged sleeve
  clears the assembled frame, panels, hardware and retained electronics at
  a measured sleeve centre of y = 2.8 mm.
- Intentional insert/pilot interference, existing simplified nut/rod overlap
  and the original snug OLED seat are distinguished from new collisions.
  The OLED mount's nominal contact matches the original assembly.
- Physical printing, insert installation, wiring clearance and tool use
  have not yet been verified on hardware.

![Panel mounting fit fixture](panel-fit.png)

![Panel mounts and shared electronics](panel-mount-detail.png)

![USB and SD rear access](rear-access.png)

![Plain spacer before owner edge finishing](plain-spacer.png)
