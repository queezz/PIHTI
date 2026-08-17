# Inventor-compatible duplicate copy paths

**Goal:** make duplicate-row Copy output paths for both distinct fields in
Inventor's Open dialog.

## Decision

- Copy the absolute Windows file path for the bottom **File name** field.
- Copy the absolute containing directory for the breadcrumb/address bar. That
  bar navigates to folders but rejects a file path, even when the file exists.

## Changed

- Duplicate member-row Copy markup and its regression test.
- README, viewer design, changelog, and tool version 0.10.2.

## Verification

- The regression assertion includes the resolved temporary workspace root and
  the complete member path.
