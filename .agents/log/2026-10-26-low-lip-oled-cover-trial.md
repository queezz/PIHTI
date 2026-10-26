# Sketch a low-lip friction-fit OLED cover

## Goal

Owner requested another design trial: expose the OLED while hiding terminals,
bolts and PCB detail, use friction retention, and keep the screen from being
buried below a tall bezel.

## Design

- Added sensor-box-oled-cover-trial.ipt and the grounded OLED cover trial
  occurrence in the existing fit assembly. It is optional and excluded from
  the completed printing bundle; no existing part geometry was changed.
- Measured all eight module bodies, the four installed M2 heads and the mount
  in the OLED's own coordinate frame. CAD active screen is 21.56 x 11.22 mm,
  glass plane 1.265 mm, screw heads 1.765 mm. Heads stand only 0.5 mm above glass.
- Made a 22.4 x 12 mm bevelled viewing opening. Narrow lip is 0.7 mm above
  glass; the surrounding face is 1.5 mm above glass, allowing 0.2 mm head
  clearance and 0.8 mm roof thickness. Glass clearance is 0.3 mm.
- Skirt wraps PCB edges, with 0.4 mm general clearance and four local 0.05 mm
  friction pads below the glass. Added 0.15 mm lead-ins for push-on assembly.
  Screw and terminal pockets are concealed on the underside. No new fasteners.
- Native dimensions are driven by named parameters. screen_lip_height really
  drives the bevel; fit_interference really drives all pad tips. Kept the
  exact old OLED/mount relationship rather than changing those working parts.
- Saved front, oblique, uncovered comparison and underside native PNG views,
  plus oled-cover-trial-check.json. Documented the trial in the folder README.

## Verification

- New part is one solid and every feature is healthy (11778).
- Initial 0.25 mm side clearance caused small contacts at the PCB corners;
  increased it to 0.4 mm. Final contact is exactly four intended PCB pads,
  0.315 mm3 total, with no glass/head/terminal/mount or other assembly contacts.
- A zero-interference parameter trial produces zero contacts against all
  existing occurrences. Restored fit_interference = 0.05 mm for the trial.
- Tested lip-height control at 0.6 mm, confirmed bevel change and actual solid
  volume change, then restored 0.7 mm. No inactive display-only fit parameter.
- Native views visually checked: active screen exposed; PCB, pins and screw
  heads hidden. Underside view shows the four pads and hardware pockets.
- Original referenced CAD part hashes were preserved; finished STL and native
  source hashes still match their unchanged printing manifest.
- notes check retains the same two unrelated summary findings; git diff --check
  passed. Native design only, so unchanged software gates were not repeated.

## Next

Review appearance and proportions. Friction retention has not been tested on
printed hardware: tune fit_interference with the actual module and process.
The existing complete STL ZIP remains unchanged and does not include this trial.
