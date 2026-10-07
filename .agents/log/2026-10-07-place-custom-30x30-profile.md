# Place variable-length 30x30 profile

## Goal and evidence
User could not place custom Al-profile-30x30 iPart at length 1000. Factory has
one 600 mm default row, length marked CustomColumn=True, valid linked user
parameter, no custom range restrictions, and healthy extrusion/pattern.
Generated native members through CreateCustomMember. Required numeric custom
input in a SAFEARRAY of BSTRs, in the table's mm units; units-appended input
failed. Explicit unique destination avoids reuse of the factory basename.

## Changes and verification
Created bwllows-probe/Al-profile-30x30-L600.ipt default member during diagnosis
and bwllows-probe/Al-profile-30x30-L1000.ipt requested custom member. Inserted
Al-profile-30x30-L1000:1 beside sliding-assembly at (-200,0,0) mm, free for user
placement. Verified native iPart membership and bounds 30x30x1000 mm. Left
assembly unsaved. Factory remains unchanged. A proposed source-row rename was
rejected by automatic review and was not executed; generation succeeded without
that change.

## Next steps
Place and constrain the inserted profile as desired. For other lengths, use
numeric custom length and a unique member destination. Save assembly when ready.
