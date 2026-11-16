# PIHTI Inventor templates

Open [PIHTI.ipj](../PIHTI.ipj) before creating or editing CAD. Its Templates
folder is set to this directory using a relative path. In Inventor's New File
dialog, select the corresponding template here.

| Template | Use |
| --- | --- |
| [Standard.ipt](Standard.ipt) | Solid part, mm / g / s |
| [Sheet Metal.ipt](Sheet%20Metal.ipt) | Sheet metal part, mm / g / s |
| [Standard.iam](Standard.iam) | Assembly, mm / g / s |
| [Standard.idw](Standard.idw) and [Standard.dwg](Standard.dwg) | Metric drawings with the Autodesk Default Standard (JIS) |
| [Standard.ipn](Standard.ipn) and [Weldment.iam](Weldment.iam) | Autodesk metric presentation and JIS weldment templates |

For background automation, pass the explicit project template path to
`Documents.Add`. In the checked Inventor 2027 session, the unqualified
`FileManager.GetTemplateFile` call still returned the installed application
template. Inventor API geometry lengths are in centimeters even when the
document displays millimeters. Prefer unit-bearing parameter expressions.

See the [Inventor automation recipes](../.agents/inventor-how-tos.md) for COM
setup, assembly context, constraints and verification. For fabricated parts,
add fillets and chamfers after the fits are established. Select exposed edges
from the current geometry, check bolt seating and tool access, and preserve
bearing seats and locating surfaces. R2 and C0.4 are specific to the bellows
mount review. Choose edge sizes for the actual part and carry required edge
finishes into its fabrication drawing.

See the [mechanical drawing references](../MECHANICAL-DRAWING.md).
