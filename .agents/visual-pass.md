# Visual pass: turning queezz's narration into folder and file notes

A visual pass is a session where queezz browses the viewer, points at a folder
or an assembly (screenshot, inspector open), and says what it is, what state it
is in, and how it is used or serviced. The agent writes that down where the
viewer shows it back. Nothing else is inferred. After a few passes the archive
carries its own basic structure without anyone filling in metadata by hand.

## Where things go

| What queezz says | Where it lands | Shown as |
|---|---|---|
| What a folder or system is, its state, how it mounts, how it is serviced | the folder's `README.md` (its folder note) | the folder card excerpt, the Note toggle, MkDocs, GitHub |
| A fact about one file: what it is, its status, that it is superseded | the file's sidecar `<cad filename>.md` (frontmatter + prose) | the tile story card, the inspector, the part page |
| "This is the main assembly" / "this is the hero" | `hero: true` in that file's sidecar frontmatter | first and larger in its folder, first in the folder strip, in the landing page's Main assemblies row |

**Sourcing.** When he says what a bought part is, where it comes from, what
it costs, or where an order stands, that lands in the folder's
`sourcing/<slug>.md` (one note per option: `title`, `vendor`, `part_number`,
`url`, `price`, `status`, `for`, `date`, then his prose), not in the folder
note or a sidecar. Screenshots and quotes he hands over go in
`sourcing/attachments/`. The same rules apply: his words and numbers only.

Cross-references between systems (this goes into that flange's CF70 opening)
belong in both folder notes, each from its own side, naming the other folder
by its path in backticks.

## Folder note shape

1. `# <folder name>` on the first line.
2. One sentence directly under the title. This is the card excerpt and the
   only thing most visitors read: what the thing is and its state.
3. Short sections with plain headings that answer what a visitor asks:
   `## Role`, `## How it mounts`, `## Servicing`, `## Status`, `## Issues`.
   Bullets over paragraphs.
4. Keep any generated inventory sections (`## Main Assembly`, `## Assemblies`,
   `## Parts`) below the authored text. They are navigation, not prose.
5. Remove the generator marker line (`<!-- This file was generated ... -->`)
   the first time a generated note is authored, so `scripts/generate_readmes.py`
   leaves the file alone from then on. Saving through the viewer does this
   automatically; a hand edit must do it too.

## Rules

- **Only the owner's words become facts.** Rephrase for grammar and structure,
  keep his terms and numbers, do not add specifications, materials, or
  purposes you read off a thumbnail or guessed from a filename. If a bullet
  cannot be traced to something he said, it does not go in. Date the
  statement in parentheses when it records state: `(owner, 2026-09-24)`.
- **Never overwrite authored text.** Add sections and a summary line; leave
  existing prose in place, typos included, unless he asks for a rewrite.
- **Do not touch CAD files.** A visual pass writes Markdown next to them and
  nothing else. Moves, renames, and hero flags are done through the viewer or
  its CLI twins so the ledger records them.
- **Sidecars are per file, whole filename plus `.md`.** `cathode-box.ipt.md`,
  never `cathode-box.md`. Frontmatter keys the viewer knows: `part_number`,
  `material`, `status`, `tags`, `supersedes`, `hero`,
  `seeded_from_iproperties`. The server refuses frontmatter it cannot parse;
  check with the gate below before committing.
- **Portable paths only.** Refer to folders by workspace-relative path in
  backticks; never a drive letter or a machine path.
- **Commit notes separately from tooling and from CAD changes**, per
  `commit-culture.md`. Notes are the owner's words; the commit title says
  which folders were documented.

## Gate

Before committing notes run, from the repository root:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup notes check .
```

It reports authored notes that still carry the generator marker, notes without
a summary sentence under the title, sidecars whose frontmatter does not
parse, and sourcing notes that do not parse or whose status is not one of the
five. The usual repository gates apply as well when tooling changed.

## Session shape

1. Orient as usual; open the viewer state he is looking at if a screenshot is
   given (the inspector names the file; the breadcrumb names the folder).
2. Write the folder note and, when he named a file, its sidecar. Set `hero`
   when he calls something the main assembly.
3. Run the gate. Tell him in two lines what landed where; the site shows it
   within a few seconds on the running instance.
4. Commit the notes with an `agent:` trailer and record the pass in
   `.agents/log/`.
