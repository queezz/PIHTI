# Inventor Workspace

Short notes for opening this repository safely in Autodesk Inventor.

---

## Open the project first

**Always open `PIHTI.ipj` before opening any assembly or part.**

The project file tells Inventor where the workspace and library folders are,
especially `ContentCenter/`. Without it, Inventor will report missing
references and may save broken links back into the assembly.

Basic sequence:

1. Open Inventor
2. File -> Open -> select `PIHTI.ipj`
3. Then open the `.iam` assembly you need

---

## Why references break

Inventor assemblies do not contain full copies of every part. They store links
to `.ipt` and `.iam` files, usually as paths relative to the project workspace.

If the project file is not active, or if files are moved outside Inventor, those
paths no longer point to the right files. The assembly then opens with missing
parts, wrong substitutes, or unresolved references.

---

## Do not open `.iam` files directly

Opening an `.iam` from Windows Explorer is risky because Inventor may not load
the `PIHTI.ipj` workspace first. The assembly might appear to open, but many
references can be unresolved in the background.

If you save in that state, the broken reference state can become part of the
file.

---

## ContentCenter

`ContentCenter/` is the shared library for common hardware and vendor-like
parts: CF/KF flanges, aluminium profiles, fittings, connectors, optics, and
similar reusable geometry.

Many assemblies across the repository reference these files in place. Treat
them as shared components. A change there can affect several systems.

---

## Renaming and moving files

**Do not rename or move `.iam` or `.ipt` files in Windows Explorer.**

Assembly references are stored inside the Inventor files. Renaming a part in
Explorer can orphan every assembly that uses it.

If a file really needs a new name or location, use Inventor tools such as
Design Assistant or Pack and Go so references are updated together with the
file.
