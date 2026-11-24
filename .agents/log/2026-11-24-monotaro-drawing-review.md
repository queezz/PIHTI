# Review the compact bellows drawing sheets

## Goal and evidence

Reviewed the current 23-page landscape A4 Bellows-Monotaro workshop PDF for
layout, typography, labels and displayed dimensions. Used the supplied Inventor
image for apparatus context and reviewed all rendered PDF sheets. Compared the
two PDF exports by extracted text and checked nine product links in each. No
native CAD, drawing or PDF edits were needed for the review.

## Findings

- Sheet 03 sends the reader to sheet 23 for vacuum flange hardware and order
  codes. Sheet 23 has no such hardware rows. Point to the Stage vacuum fasteners
  section of the basket audit or add a compact fitted-hardware table on 23.
- Sheet 07 puts all three slot dimensions and their extension lines in the
  bottom-left slot in the parent view. Move 5.5, 8.5 and 3 to one enlarged
  typical-slot detail. Leave the location dimensions and the eight-slot leader
  on the parent view. Move the M5 leader text clear of the quantity heading.
- Sheet 10's orientation note is nearly on the bottom border. Move the lower
  view and caption upward or place the orientation note beside the view.
- Sheet 12 shows the Ø12 journal fit as an unresolved shop proposal. If the
  assembly needs a controlled finished overall length after facing, specify it
  separately from the 1000 mm stock reference. The fit remains an open decision
  for the shop and owner.
- Sheet 01's paired balloons 11/14, 15/16 and 17/18 are hard to associate with
  individual parts. Use distinct leaders where both targets are visible and
  point to the assembly detail where one part is hidden. Left-align the part
  names in the index table. Use the available note space on 12 and 19/20 to
  distinguish machining instructions from assembly explanation.

## Fleet purchase handoff

Fleet Post `20261124-2bbe56c3-0289ff` was imported with recipient verification.
Attachment `monotaro-order-124033110005.md` matched SHA-256
`f3b830a4f3e3fd29a51b8d743893f83aec915d8266a0750cd221d6486f0e6228`.
The post was marked collected after recording the handoff.
The 24 November supplier confirmation lists 27 unique order codes and a total
of ¥124,027 including ¥11,275 tax. Line extensions sum to ¥112,752 before tax.

The order covers the two rail sets and two separate guide blocks, 40 rail
screws, and the selected ESCO hardened washers (ten). The 42209456 BUMAX 109 M6
support nut specified on sheets 03 and 21 is absent from the confirmation.
The M6 nuts that do appear are 28763685 vacuum joint nuts, listed separately
from the support nuts in the audit. Confirm the source of the four support
nuts at assembly. The rail set's supplier dispatch estimate was 4 December.

## State

The saved-file STEP status reports 1,080 models, 1,075 current mirrors, four
stale, one missing and zero STEP preflight Doctor blockers. The top-level
apparatus shown in the screenshot has a stale mirror and a pre-existing
working-tree change. The previous native handoff verified 373 attached
annotations and resolved drawing references. Native health was not rechecked
in this PDF review. `git diff --check` passed.

## Drawing updates after the review

Queezz asked to apply the fixes. Sheet 01 now gives each clamp half a leader,
left-aligns part names and points to the assembly detail for the hidden nut
and retaining washer. Sheet 07 adds a 3:1 native detail with associative
8.5, 5.5 and 3 mm slot dimensions and moves the M5 callout. The existing
slot locations remain on the main view. Sheet 10 puts the orientation note
beside its view. Sheet 12 places the pending Ø12 fit beside the journal
dimensions. Sheets 19 and 20 separate bearing dimensions from assembly steps.

Sheet 23 now lists the five fitted vacuum fastener lines referenced from
sheet 03, with product links. Sheets 21 and 23 call for confirming the source
of the four BUMAX support nuts. The basket record now cites the actual order
confirmation and keeps the screenshot quantities as historical audit evidence.

Changed paths: `Bellows-Monotaro-A4-JIS.idw`, the two PDF variants,
`monotaro-pdf-links.json`, and `monotaro-basket.md` in `bellows-probe/`,
plus this log. The native changes were trialed in an invisible copy and only
the drawing was saved. The assembly and part model geometry were not edited.

Verification: 23 landscape A4 sheets, 92 resolved model documents, 375
attached annotations and current drawing views. The installed drawing
reopened cleanly and no task-owned background documents remained. Measured
the new slot dimensions on their native geometry. Rendered all sheets and checked
the changed layout and confirmed the two PDFs have identical text and the
same 14 product links, each covering its printed code. STEP status matched
the baseline above. Pytest passed all 543 tests and Ruff passed.
