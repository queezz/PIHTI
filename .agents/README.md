# .agents/

Operational memory and workflows for AI-assisted work on this engineering
archive. Read the repository root `AGENTS.md` first, then this file and the newest
entry under `log/`.

This is kept separate from `docs/`:

- `docs/` - durable, published documentation about PIHTI hardware and repo workflows.
- `.agents/` - directions, decisions, inventories, workflows, and handoffs. Not
  published to the MkDocs site.

## Layout

- `../README_SHORT.md` - pasteable cold-start route; it points here rather than
  duplicating the repository rules.
- `REPOSITORY_MAP.md` - folder roles and project boundaries.
- `directions.md` - forward-looking open work only.
- `CHANGELOG.md` - shipped archive milestones.
- `log/` - dated session handoffs going forward.
- `commit-culture.md` - repository commit contract.
- `duplicate-inventory-direction.md` - safe duplicate review workflow.
- `dedup-viewer-design.md` - local duplicate-review viewer architecture.
- `handoff-template.md` - copy-paste session-log skeleton.

The dated Markdown files directly under `.agents/` are legacy June 2026
handoffs. They remain at their committed paths; create new handoffs in `log/`.

## Naming convention

One file per session/handoff under `log/`, named:

```text
YYYY-MM-DD-short-title-kebab.md
```

Examples:

```text
2026-06-22-boron-probe-inventory.md
2026-07-02-sample-holder-integration.md
```

If two handoffs land on the same day, append a counter.

## What goes in a handoff

Keep it short and skimmable:

- **Goal** - what this session set out to do.
- **Decisions** - choices made and why.
- **Changed** - files/commands added or modified.
- **State** - what works now and what was verified.
- **Next** - the obvious next steps.

See [`handoff-template.md`](handoff-template.md) for a copy-paste skeleton.

## Artifact types

Use the file format to signal the intended reader:

- `*.md` - human and agent orientation: goals, decisions, evidence summaries, cleanup plans, and next steps.
- `*.json` / `*.csv` - machine-facing inventories and raw analysis outputs, especially duplicate/hash scans.

Avoid committing generated mechanical Markdown reports. If a tool can emit both JSON and Markdown for the same inventory, keep the JSON as the durable machine record and write a short Markdown summary only when human judgment or handoff context is needed.

## Standing directions

- [duplicate-inventory-direction.md](duplicate-inventory-direction.md) - bit/hash inventory workflow before CAD cleanup or staged imports.
- [dedup-viewer-design.md](dedup-viewer-design.md) - architecture and safety
  boundary for the paperlib-style duplicate review server.

## Cold sessions

Start at [`../README_SHORT.md`](../README_SHORT.md), then follow its ordered
list. `AGENTS.md` is the repository authority; fleet `RULES.md` and `MAP.md` are
read afterwards for shared culture and sibling boundaries. If those sources
disagree, stop and report the exact conflict instead of blending the rules.
