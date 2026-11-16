# Hand off the Inventor assembly and drawing workflow

- Extended the Inventor how-tos with drawing-only carriage positions, upright camera setup, native section and bore centerlines, sheet order, and PDF stroke-width verification. Recorded the background-document cleanup guidance in AGENTS.md.
- The latest 17-sheet shop PDF contains the centerlines, horizontal wheel-flat section, and thinner vector strokes. It remains a local export under the existing Git exclusion. The tracked IDW does not contain those last revisions. The owner reported that the attempt to stop the active render crashed the Inventor session. All subsequent handoff checks used files on disk.
- Collected the saved wheel, assembly and retracted-view image and the Miura archive with its existing handoff. No pending Inventor edits were included.
- Ruff and diff whitespace passed. The full test run passed 527 tests and timed out in the isolated STEP worker test. That test passed on its own in 2.05 seconds. No tooling source changed.
