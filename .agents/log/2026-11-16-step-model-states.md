# Preserve Inventor model states in the STEP mirror

- Goal: preserve Primary, Boron Hayashi and Permeation as separate exports and
  keep the way back to export controls visible after an Inventor timeout.
- The explicit assembly action enumerates saved model states and requests each
  by name, verifying the document's state before export. It uses the normal
  no-open-document guard and leaves the ordinary mirror untouched.
- Variant manifests use the assembly's saved file stamp. The STEP viewer and
  the assembly page link only current variants. No CAD changes.
- Changed Inventor/session export, mirror and viewer lookup, part/results/history
  pages, tests, version and changelog.
- Automated tests use an Inventor double; live geometry verification needs the
  assembly saved and closed in Inventor. Next: export all states from the vessel
  file page and inspect Permeation, especially its probe occurrence.
