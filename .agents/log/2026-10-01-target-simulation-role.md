# Target simulation role

## Goal and decisions
The user needs additional simulation roles, specifically target, and accepts
hardcoded options for now. Added target to the shared role registry with amber
preset #df935b. The existing template, validation and export pipeline use this
registry; no geometry or existing metadata was changed. Asked which additional
roles the user wants; none were specified during implementation.

## Changed paths
simulation_step.py, package version and pyproject.toml (0.30.5), changelog and
this log. Unrelated archive work remains outside the commit.

## Verification
Verified the rendered target option, saving target metadata, and strict bundle
export using a temporary two-occurrence STEP fixture. Ruff passed. Full pytest
and diff checks recorded in the commit verification.

## Next steps
Restart pihti through the owner's Lab terminal to refresh cached role options.
Add additional named roles when specified.
