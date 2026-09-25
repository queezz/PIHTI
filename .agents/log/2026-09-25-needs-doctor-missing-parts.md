# Needs-Doctor catches plainly missing parts (pihti-dedup 0.27.1)

**Goal:** the STEP mirror must not open an assembly that makes Inventor raise
Resolve Link for a part nobody has. `BoronProbe_2026/parts/C25K22A4CU.iam`
names vendor parts that lived on a student's OneDrive; the 0.24.4 rule
(duplicate name, or missing old name of an open ledger rename) let it
through, and the batch hung on the dialog. Resolves the directions item
"Needs-Doctor misses plain missing parts".

## Decisions

- Rule (`step_mirror.reference_problems`, used by `first_blocking`,
  `blocking_reference`, `StepMirror.blocker`, and Doctor's queue): for each
  `.ipt`/`.iam`/`.ipn` name an `.iam` embeds, URL-decoded and casefolded,
  minus the ledger's repaired/indirect pairs:
  - two or more workspace files → "<name> exists N times" (unchanged);
  - no file outside `OldVersions/` → "<name> is missing", unless exempt:
    the name is a settled rename's old name (`retired_names`), Inventor finds
    it outside the workspace (`resolves_outside`), or it is the tail of a
    longer name the same assembly embeds, cut mid-word (`rd (mm).iam` inside
    `Standard (mm).iam`: the byte scan splits a name that crosses a storage
    sector). An open ledger rename's old name is never exempt.
- `.idw` names stay out of the check, as in 0.24.4 (an assembly never opens
  a drawing; the existing test says so). On this tree no assembly embeds a
  missing `.idw` name that is not a template, so the result is the same.
- `resolves_outside` / `OutsideNames`: Inventor's template names (built-in
  list of the standard, sheet metal, weldment, mold, and drawing template
  names, plus every file under `%PUBLIC%\Documents\Autodesk\Inventor
  <version>\Templates`, language subfolders included;
  `PIHTI_DEDUP_INVENTOR_TEMPLATES` overrides), and files under the Content
  Center Files folder or a project library folder. The Content Center folder
  is, in order: `PIHTI_DEDUP_CONTENT_CENTER`; the project file's own entry
  (`ContentCenterFolder/Path`); `%USERPROFILE%\Documents\Inventor\Content
  Center Files` (Inventor's per-user default, the one this machine uses);
  `%PUBLIC%\Documents\Autodesk\Inventor <version>\Content Center Files`,
  newest first. Library folders: `ProjectPath pathtype="Library"` and
  `LibraryPath` entries. PIHTI.ipj (UTF-16 XML) names only the library list
  and workspace `.`, so the per-user default is what resolves here. No
  machine path is in code or docs; everything is resolved at runtime.
- Name sets are cached per process: templates once per folder list; a
  Content Center or library folder is walked again when its own or its first
  two levels' mtimes change (a new standard family) or after 300 s (a new
  size in an existing family). `OldVersions` inside those folders is skipped.
- Doctor's **Missing file** section keeps the ledger's open renames and adds
  every name the rule counts as missing in an `.iam`; the Assemblies counts
  use the same classification. Doctor also covers `staging/` assemblies (it
  always did); the mirror does not.
- Tests never read the machine's Templates or Content Center folders:
  `conftest.py` points both overrides at empty folders per test.

## Real tree (read-only, Inventor closed)

`step-mirror status .`: 908 Inventor files, 905 current, 3 missing, and

```
need Doctor: 3
  TempController.iam: RKC CONTROLLER.ipt exists twice  (ElectronicsBox/TempController)
  cosel-psu-din-clip.iam: manometer-bracket.ipt is missing  (ElectronicsBox/Win-GPIO-Box)
  C25K22A4CU.iam: ICF70F 1個付き 19穴.ipt is missing  (BoronProbe_2026/parts)
```

Across all 239 in-scope assemblies (908 files) the rule blocks 32: the 27 of
0.24.4 (24 duplicate-name bundles plus the Wide Din Clip referrers) and five
new plain-missing ones: `C25K22A4CU.iam` (ICF70F 1個付き 19穴.ipt,
W5K22A4CU*.ipt/.iam), `C70TCK2MBGA.iam` (ICF70FLMG4MBA.ipt, WTCK2MB*),
`BoronProbe_2026_exploded.iam` (BoronProbe_5_disassembled.iam),
`BoronProbe_2026_non-bellows.iam` (ICF70-34-hole.ipt), and
`OLED 2.42 12864.iam` (OLED 2.42 12864 v7.iam). Only the three above are in
the export queue; the others already have current STEPs. Before the
fragment exemption the count was 37 (Fuse Holder and R_Axial on
`rd (mm).iam`, Rotary_Feedthrough on `ary_handle.ipt`, two ESP32 import
assemblies on cut names). `Standard (mm).iam` (221 assemblies) and
`Standard (in).iam` (18) are the template exemptions; no Content Center
name occurs in any assembly on this tree.

Caveat: the export log shows the four new non-queue assemblies exported
without a hang on 2026-09-25, so their missing names may be fossils
(save-as sources, an old vendor import). They are listed in Doctor for the
owner to judge; `step-mirror export --force` still exports one named file.

## Changed paths

- `src/pihti_dedup/step_mirror.py` — `reference_problems`, `retired_names`,
  `OutsideNames`, `resolves_outside`, `project_file`, `project_folders`,
  `content_center_folder`, `template_folders`, `template_names`,
  `folder_names`; `StepMirror(retired=, outside=)`; module docstring.
- `src/pihti_dedup/whereused.py` — `decoded_name` (moved from web).
- `src/pihti_dedup/web.py` — mirror wiring, Doctor queue classification.
- `src/pihti_dedup/cli.py` — `_attach_references` passes retired names.
- `tests/conftest.py`, `tests/test_step_mirror.py`, `tests/test_web.py`.
- `pyproject.toml`, `src/pihti_dedup/__init__.py` — 0.27.1.
- `README.md`, `.agents/dedup-viewer-design.md`, `.agents/CHANGELOG.md`,
  `.agents/directions.md`.

## Verification

- pytest 485 passed, fresh basetemp; ruff clean; `git diff --check` clean.
  README.md is not under `docs/`, so no MkDocs build.
- No real Inventor reached; the owner's viewer on 127.0.0.1:4185 untouched.

## Next steps

- Owner: look at the five new needs-Doctor assemblies in Doctor; if the
  ICF70/W5K22A4CU/WTCK2MB vendor parts can be recovered from the student,
  add them; otherwise decide per assembly (leave out of the mirror, or
  repoint).
- Not committed.

## Usage

- Provider: Anthropic; implementation agent: Claude Opus 5.5; observed
  2026-09-25 JST.
