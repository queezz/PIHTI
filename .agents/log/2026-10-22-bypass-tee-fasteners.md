# Fit workspace bolts to the bypass tee

## Goal and choice

Fit the two connected CF70 tee flanges with local workspace hardware.
The tee-to-bellows adapter has six M6 tapped holes; the gauge-port connection
has six through holes. The tee flange is 12.7 mm thick and its gauge-port mate
is also 12.7 mm thick, so existing M6x25 bolts cannot span that stack plus nuts.

## Changes

- Added six ContentCenter/Fastners/M6x25-HexCS.ipt bolts at the tapped adapter.
- Created M6x35-HexCS.ipt as an independent Inventor copy of M6x25-HexCS.ipt,
  changed NLG to 35 mm and assigned its distinct part number. Original bolt
  source unchanged.
- Added six M6x35 bolts and six existing M6-nut.ipt nuts at the gauge-port
  through-hole connection. All hardware files are under ContentCenter/Fastners.
- Added 18 rigid joints, one per fastener; bolt heads seat on the tee's rear
  flange faces, nuts on the gauge-port adapter's rear flange face.
- Saved sliding-assembly.iam only. User closed Inventor documents during the
  task; reopened the saved target under PIHTI.ipj and continued in background.

## Verification

- Exactly 12 bolts and 6 nuts, each with one healthy rigid joint (102401).
- All new joint origin pairs coincide within 0.00001 mm; bolt and nut axis
  directions checked against the intended flange sides.
- All 18 native document paths are workspace fastener paths.
- All active relationships in sliding-assembly and its reopened
  PIHT-Bellows-probe parent healthy after update.
- Native bitmap inspected. git diff --check passed. No software changed;
  earlier same-session Ruff and 525-test pass cover the unchanged tooling.

## Next

Open bypass branch left available. Other owner CAD and metadata edits remain
outside this scoped commit. No washers, gaskets or bypass plumbing added.
