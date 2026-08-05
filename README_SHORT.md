# PIHTI — Short Orientation

Paste the starter prompt below into a cold agent session. This file is a route
into the repository's maintained instructions, not a second copy of them.

## Where this is

```text
<Dropbox>/Drawings/PIHTI
```

`<Dropbox>` means the machine-local Dropbox root. The repository root is also
the Autodesk Inventor workspace; `PIHTI.ipj` is the active project.

PIHTI is the curated hardware archive. Recent student submissions remain in
review-oriented trees such as `BoronProbe_2026/`, `Plasma Vessel_2026/`, and
`bellows/`; a merged folder is not automatically canonical hardware.

## Hard boundaries

- Open `PIHTI.ipj` before Inventor assemblies or parts.
- Unique filenames are enabled. A repeated CAD filename anywhere in the
  workspace is an Inventor-resolution concern.
- Do not rename or move Inventor files outside Inventor until references have
  been checked.
- Hash equality proves identical bytes, not canonical ownership or safe
  reference replacement.
- Duplicate cleanup is preview-first and recoverable; committed CAD removals
  must be separate from tooling changes.
- Use the external `~/.venvs/pihti-dedup` environment and launch the viewer with
  `lab pihti`. Never create a venv inside Dropbox.

The detailed and authoritative rules are in `AGENTS.md`. Fleet context is read
after PIHTI's files and does not replace them.

## Starter prompt

Orient in `<Dropbox>/Drawings/PIHTI`. Read, in order: `README_SHORT.md`,
`README.md`, `.agents/README.md`, the newest `.agents/log/` entry,
`.agents/duplicate-inventory-direction.md`, then fleet `RULES.md` and `MAP.md`
from `<Dropbox>/20-Code/fleet`. Use `.agents/REPOSITORY_MAP.md` for boundaries,
`.agents/directions.md` for open work, and `.agents/commit-culture.md` before
committing. The repo is an Inventor workspace: open `PIHTI.ipj`, treat duplicate
filenames as resolution risks, and do not infer canonical files from hashes.
Use `~/.venvs/pihti-dedup`; launch through `lab pihti`. Run the gates in
`AGENTS.md`, stage explicit paths, keep tooling and CAD cleanup in separate
commits, put earned versions in commit titles and both version files, end
agent-written commits with `agent: <name>`, and write a dated handoff.
