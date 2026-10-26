# Modular sensor box print files

High-resolution binary STLs in millimetres, exported from the finished Inventor parts on 2026-10-26.

Use `modular-sensor-box-high-res.zip` for the complete bundle, or import the
individual STL files. All original body meshes passed watertightness, winding,
positive volume and dimension checks against their native solids. Detailed settings,
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
| `modular-box-case.stl` (includes grips) | 1 |
| `modular-box-retainer.stl` | 1 |
| `sensor-box-oled-sleeve.stl` (friction-fit trial) | 1 |

Double the quantities for two complete boxes. The four `sensor-box-*` files
are the new panels and mounting spacers; the remaining files are the shared
printed components. The enclosure's case and grip bodies are together in
`modular-box-case.stl`, in their original multibody positions. The grips are
part of the case print and receive the owner's fuzzy-skin settings. The retainer
remains a separate STL; do not print a separate grip file.

## Slicer setup

- Interpret coordinates as millimetres, at 100% scale.
- Front and back panel STLs already lie outside-face down at Z = 0, with
  the mounting ears pointing upward. Their footprints are 74 x 60 mm; heights
  are 11 mm (front) and 19 mm (back).
- The OLED sleeve STL lies display-face down at Z = 0, cavity and grips up.
  Its outer front edge is a 0.6 mm chamfer; print size is approximately
  31.6 x 35.71 x 15.54 mm in this orientation. The owner's width adjustment is retained with symmetric enlarged side knobs and
  two 1 mm internal stops taking up vertical play. This revised fit needs
  a test print.
- Other parts retain native CAD orientation and placement. Orient those parts
  and place them on the build plate in the slicer; the retainer in particular
  retains its original offset coordinates.
- The case STL preserves both original body meshes without a Boolean union
  or remeshing, for the existing grip fuzzy-skin workflow in the slicer.
  The case and grips are touching closed volumes, kept as a multibody print.
- Both panels have 4 mm ears. The named `ear_thickness` parameter drives all
  four ear profiles and their screw-clearance depth in each native panel.
- Spacer screw pilots are 2.5 mm for the owner's direct M3-in-plastic approach.
  No heat-set inserts are included.
- These are the owner's final finished models, including the latest fillets
  and chamfers. Working panel openings were not redesigned during export.

## Export settings

Inventor High preset, binary STL, explicit millimetre units, no colour data,
and no movement of internal mesh nodes. Case and grip bodies share one file;
other printable parts have their own files.
The exporter options are documented in the
[Autodesk translator reference](https://help.autodesk.com/cloudhelp/2022/ENU/Inventor-API/files/TranslatorSettings.htm).

The panel meshes were subsequently rotated and translated for face-down
printing, without remeshing or changing their geometry. The OLED sleeve was
exported from a rigidly transformed temporary solid with its front face down. Their exact rigid
transforms are recorded in the manifest. Native CAD models remain unchanged.
