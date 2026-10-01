# MeanWell solid-body colours

## Goal and decisions

Investigate the MeanWell colour exceptions reported after 0.30.2.
RT-65D colours are stored on solid bodies, with no explicit face styles.
The reader now propagates solid colours to faces unless a face overrides them.
OCP shape wrappers compare by Python identity, so topology lookup uses hash
buckets plus IsSame rather than wrapper equality. No CAD or mirror changes.

## Changes

simulation_step.py, a solid-colour/face-override regression in
test_simulation_step.py, synchronized tool version 0.30.3 and changelog.

## Verification and remaining boundary

The actual RT-65D assembly mirror now yields nine body colours, including
yellow, blue and green. The vendor RT-65D STEP also stores those colours.
The LRS-100-12 vendor STEP has grey, yellow and black, but its Inventor mirror
contains only one grey COLOUR_RGB record. Reader changes cannot reconstruct
colours absent from that export. Its Inventor appearance/export needs inspection;
do not substitute vendor geometry for the current Inventor model silently.

Focused tests passed, including five inherited yellow faces and one blue face
override. Full suite: 504 passed; Ruff and diff whitespace checks passed.
The actual RT-65D mesh ranges also contain all nine inherited colours.
Unrelated CAD work and the rename ledger are excluded from this commit.
