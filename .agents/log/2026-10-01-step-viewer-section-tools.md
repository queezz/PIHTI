# STEP viewer orientation and sections

## Goal
Give the large STEP viewer the inspector's orientation and section tools.

## Decisions and changed paths
Reuse the shared mesh-tools template and PihtiMeshTools controller. Hide the
Still/3D toggle in this always-3D page, wrap controls within the right rail, and
initialize after deferred shared scripts load. Remember orientation per source;
reset sections when opening a model. Cuts remain display-only.

Changed simulation.html, _file_tile.html, simulation.js and dedup.css. Bumped
pyproject.toml and package version to 0.30.4 and recorded the changelog entry.

## Verification
504 pytest tests passed; Ruff and JavaScript syntax checks passed. Browser QA
used an isolated Lab service with a copied 55-part STEP, redirected cache and
mirror, and automatic refresh disabled. Verified Y/Z orientation, all three
section axes, slider, Off, selection, isolation, fit and reload. Reload retained
Y-up and cleared the cut. Visually inspected the section through the assembly
at the browser's 1280x720 viewport; controls fit inside the scrolling rail.
Visited all surrounding navigation routes successfully. Owner's port-4185
service was left running; its cached templates need an ordinary Lab restart.

## Next steps
Run lab restart pihti in the owner's terminal, then reload the STEP viewer.
Tungsten consolidation still needs the requested occurrence identification.
Unrelated CAD/archive edits were left out of this commit.
