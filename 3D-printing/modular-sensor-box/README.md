# Modular sensor box print files

High-resolution binary STLs in millimetres, exported from the finished Inventor parts on 2026-10-26.

Use `modular-sensor-box-high-res.zip` for the complete bundle, or import the
individual STL files. All eleven files passed watertightness, winding, positive
volume and dimension checks against their native solids. Detailed settings,
source hashes and mesh checks are in `export-manifest.json`.

## Quantities per complete box

| STL | Quantity |
| --- | ---: |
| `sensor-box-front-panel.stl` | 1 |
| `sensor-box-back-panel.stl` | 1 |
| `sensor-box-upper-mount-spacer.stl` | 4 |
| `sensor-box-lower-mount-spacer.stl` | 4 |
| `modular-box-base-plate.stl` | 2 |
| `modular-box-shelf.stl` | 1 |
| `modular-box-short-spacer.stl` | 4 |
| `modular-box-oled-mount.stl` | 1 |
| `modular-box-case.stl` | 1 |
| `modular-box-retainer.stl` | 1 |
| `modular-box-grip.stl` | 1 |

Double the quantities for two complete boxes. The four `sensor-box-*` files
are the new panels and mounting spacers; the remaining files are the shared
printed components. The unchanged enclosure's named solid bodies are exported
separately as case, retainer and grip.

## Slicer setup

- Interpret coordinates as millimetres, at 100% scale.
- Files retain native CAD orientation and placement. Orient each part and
  place it on the build plate in the slicer; the retainer and grip in particular
  retain their original offset coordinates.
- Both panels have 4 mm ears. The named `ear_thickness` parameter drives all
  four ear profiles and their screw-clearance depth in each native panel.
- Spacer screw pilots are 2.5 mm for the owner's direct M3-in-plastic approach.
  No heat-set inserts are included.
- These are the owner's final finished models, including the latest fillets
  and chamfers. Working panel openings were not redesigned during export.

## Export settings

Inventor High preset, binary STL, explicit millimetre units, one file per solid
or single-body part, no colour data, and no movement of internal mesh nodes.
The exporter options are documented in the
[Autodesk translator reference](https://help.autodesk.com/cloudhelp/2022/ENU/Inventor-API/files/TranslatorSettings.htm).
