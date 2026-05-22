# Contributor Workflow

Practical notes for students and collaborators working in this repository.

---

## Before you open anything in Inventor

**Always open `PIHTI.ipj` first.**

The project file tells Inventor where to find library components, especially the
`ContentCenter/` folder. If you open an `.iam` directly without loading the project,
Inventor will report missing references for almost everything and may silently break
links when you save.

Steps:

1. Open Inventor
2. File → Open → navigate to `PIHTI.ipj`
3. Then open the assembly you need

---

## Working with files

**Do not rename or move `.iam` or `.ipt` files outside of Inventor.**

Assembly references are stored as relative paths embedded inside each file. Renaming
a part in Windows Explorer orphans every assembly that uses it. If you need to
rename, use Inventor's Pack and Go or the Design Assistant.

**Keep changes localized to your subsystem.**

If you are working on `Plasma Vessel/Plasma-Flange-2024/`, make changes there.
Avoid touching shared library parts in `ContentCenter/` unless that is specifically
what you are here to do — changes there propagate to every assembly that uses them.

**Use meaningful filenames.**

`flange-adapter-CF70-to-KF40.ipt` is useful. `Part47_final2.ipt` is not. The
folder and filename are often the only context available when the file is opened
without this documentation.

---

## Submitting a pull request

**Include screenshots when the change is geometric.**

A rendered view or drawing snapshot in the PR description communicates more than a
diff of a binary `.iam` file. Export a PNG from Inventor or a screenshot of the
assembly with the changed part highlighted.

**Export STEP for significant new assemblies.**

When a design is substantially complete or has been physically fabricated, export a
STEP file alongside the `.iam`. This allows the geometry to be inspected without
Inventor and gives a stable reference point for that revision. Put it in the same
folder as the assembly.

**Describe what changed and why.**

"Updated flange inner diameter to 70.5 mm to match new tube stock" is useful.
"Updated files" is not. The PR description is the only narrative record of design
intent that survives past the commit.

**Do not copy entire directory trees unnecessarily.**

If you are iterating on one sub-assembly, work in that folder. Do not duplicate a
large folder and start a new parallel tree unless the old design needs to be
preserved intact as a reference. If you do need to preserve the old version,
`OldVersions/` inside the folder is the conventional location.

---

## File hygiene

- Delete `.lck` files before committing if Inventor left them behind
- Do not commit `~$` temporary files
- `OldVersions/` folders are ignored by git — Inventor manages them automatically,
  leave them alone
- Large binary files (`.iam`, `.ipt`, `.idw`) are version-controlled as blobs;
  diffs are not meaningful, but the history is still useful as a coarse changelog

---

## If something looks wrong

Check whether there is a newer version in a sibling folder before concluding the
design is broken. Several subsystems exist in multiple generations (e.g.
`TempController` and `TempController-v2`). The most recently modified folder is
usually the current working state.
