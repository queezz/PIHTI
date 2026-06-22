# .agents/

Working logs and handoffs for AI-assisted sessions on this engineering archive.

This is operational scratch space, kept separate from `docs/`:

- `docs/` - durable, published documentation about PIHTI hardware and repo workflows.
- `.agents/` - session-by-session logs, decisions, searches, and handoffs. Not published to the MkDocs site.

## Naming convention

One file per session/handoff, named:

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
