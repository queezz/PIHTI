# Commit Culture

Standing conventions for this repo. Not a dated handoff; keep this current when the workflow changes.

## Authorship

- Do not add an AI as a git co-author. No `Co-Authored-By` trailer.
- If an agent materially writes a commit, end the message with a single agent line, for example:

```text
agent: codex gpt-5
```

Human-authored commits can omit the line.

## Commit messages

- Short title, no trailing period. State the change, not the diff.
- Body: one or two sentences of context, then bullets when useful.
- Keep one cohesive change per commit.
- Add paths deliberately; do not use `git add -A` blindly.

## PIHTI repo notes

- This is an Autodesk Inventor workspace. Be careful with generated caches, lock files, and `OldVersions/`.
- Do not commit `_site/`; it is the MkDocs build output.
- Do commit durable docs and intentionally curated CAD/source files.
- When docs nav changes, run a MkDocs build before committing if the local environment is available.
