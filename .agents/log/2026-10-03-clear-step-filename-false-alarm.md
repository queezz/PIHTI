# Clear simulation STEP reference false alarm

## Goal and evidence
The site blocked the saved simulation assembly on ma_box.ipt although Inventor
opens it. Inspected its binary filename scan and running Inventor descriptors.
The scan finds ma_box.ipt, an apparent truncated plasma_box.ipt string; no
Inventor ReferencedFileDescriptor names ma_box.ipt. Active document was clean
and saved. Missing document flags exist only on the three suppressed window
mesh components, unrelated to this filename alarm.

## Changes
Used the existing record_reference_verification API to register the assembly /
ma_box.ipt pair with Inventor version evidence in the reference-verification
ledger. No CAD links or filenames were changed and no precheck rule disabled.
Explicitly exported the saved active document to the STEP mirror via SaveAs copy,
atomic replacement and normal mirror export recording. Owner service kept running.

## Verification
Fresh STEP has 78 occurrence parts; every shape passes BRepCheck_Analyzer.
Live /step-mirror response no longer reports References ma_box.ipt.

## Next steps
Reload the site to see the current mirror. The other BoronProbe missing-file
block was outside this request and remains unresolved.
