# Match clamp feet up direction

Flipped clamp-foot:1 to match clamp-foot:2's local Z direction in active
bwllows-probe/sliding-assembly.iam. Preserved its constrained/free status and
locating relationships to flange-camp-114:2 and linearbearing:3. Swapped the
contact references in Mate:11 and Mate:8 between the foot's local Z=0 and Z=15 mm
faces, keeping the mate contact senses and zero offsets. Converted Flush:6 on
its YZ origin plane into a zero-offset mate for the reversed local X direction.
Flush:5 and Flush:7 remain unchanged. No parts were edited or newly grounded.

Verified all assembly constraints healthy, and feet local Z dot product equals
1 within 1e-7. Left unsaved for user review. Unsuccessful transaction attempts
were rolled back before the verified change.
