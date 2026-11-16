# Miura membrane experiments

This retired setup comes from Miura-kun’s experiments. It was used with PdCu and Ni membranes and for the first LIBS trials. The probe is now in use, and a new bellows stage is planned.

- [Membrane-flange-V2.iam](Membrane-flange-V2.iam) shows the CF152 flange with a CF70 connection on each face and two CF34 ports.
- [MembraneFlangeWithGV.iam](MembraneFlangeWithGV.iam) shows the flange with the CF70 membrane nipple and gate valve.
- [152-double-70.ipt](152-double-70.ipt) is the flange body. The original [DWG](Membrane-flange-V2.dwg) and [PDF](Membrane-flange-V2.pdf) are included.

The source is the PIHTI-Leprecon archive. The setup reuses the two byte-identical nipple parts already in [ContentCenter](../ContentCenter/CF-parts/CF70-nipple/). Inventor resolved the imported drawing and assembly references to workspace files. The legacy nipple subassembly resolved both part references, but its standalone regeneration returned an Inventor error. The flange and gate valve assemblies regenerated.
