# Record the verified STL printing workflow

- Goal: Kuzmin requested STL export rules in the CAD how-tos after rejecting
  the coarse default Inventor STL.
- Changed `.agents/inventor-how-tos.md`: print-folder destination, explicit
  resolution checks, saved-solid STEP fallback with the tested Open Cascade
  recipe, units, independent mesh checks and replacement/reload workflow.
- Distinguish Open Cascade deflections from Inventor translator controls and
  retainer-specific evidence from universal thresholds.
- Verification: reviewed recipe against the completed retainer export and
  checked the documentation diff for whitespace. No software tests needed.
- Documentation-only work; no Inventor access or CAD modifications.
