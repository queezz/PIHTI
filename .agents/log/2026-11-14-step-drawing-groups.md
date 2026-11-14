# Select and name groups for apparatus drawings

- Goal: let the owner select complete assemblies, drill into subassemblies,
  and combine parts across depths for drawings without assigning electrical roles.
- The viewer builds a tree from STEP occurrence paths. Branch Select acts on
  its descendants; additive selection works in the tree and the model.
- Groups live in `simulation/drawing-groups.json` keyed by source and stable
  occurrence keys. Guarded updates check model hash and group revision.
  Missing occurrences are reported when recalled. CAD and export geometry
  and the simulation map remain independent.
- Changed the STEP viewer template, scripts and styles, model/group endpoints,
  persistence regression, version and changelog.
- Browser fixture verified branch selection, subtracting and adding a nested
  branch, then saving and recalling a group after reload. Pytest covers
  persistence, revision conflicts, guard, removal and map independence.
- Next: name the real apparatus groups in the viewer. Group labels are
  viewer annotations; they are not drawing callouts or STEP assembly edits.
