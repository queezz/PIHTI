# Mechanical drawing references

- [JIS B 0001 — Mechanical engineering drawings](https://webdesk.jsa.or.jp/books/W11M0090/index/?bunsyo_id=JIS+B+0001%3A2019)
- [ISO 128-2 — Basic conventions for lines](https://www.iso.org/standard/83355.html)
- [ISO 129-1 — Presentation of dimensions and tolerances](https://www.iso.org/standard/64007.html)

On symmetric parts, draw the axis with the drawing standard's centerline
style. Dimension the full center-to-center span where it controls the fit of a mating part. Use a centerline offset where that offset controls the fit. Use a section
to show depth and countersink direction, and put pitch with the hole callout.
Use functional nominal dimensions and specify tolerances separately.

Repository examples include [PALP desk](Drawings-PDFs/palp-desk.pdf) and
[plasma mesh holder](Drawings-PDFs/plasma-box-probe-window-mesh-holder.pdf).

## Shop drawing review

- Use the plan for mating spans, hole counts and pitches. Put each dimension
  on the view that shows the feature.
- Use a cut through the feature for counterbores, reliefs, seats and wall
  thickness. Use short leaders to identify the operation and its extent.
- Check the IDW against the part and mating assembly. Inspect the complete
  A4 print preview for clipped text, crossed callouts and duplicate dimensions.

- Add a center mark at each hole center in plan. Concentric bores share one mark.

- Give each fabricated part its own sheet. Use the fewest views that locate
  the features. Use a hatched section through the feature for thickness
  and bore steps.
- Show small edge breaks with a chamfer callout. Suppress redundant chamfer
  edge lines in the plan when the outline and callout describe them.
