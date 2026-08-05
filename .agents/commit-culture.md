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

- Use an imperative, sentence-case title of roughly 50–60 characters, with no
  trailing period. State the user-observable change, not the diff.
- Body: one or two sentences of context, then bullets when useful.
- Keep one cohesive change per commit.
- Add paths deliberately; do not use `git add -A` blindly.
- A commit that earns a tool-version bump includes it in the title, for example
  `Add guarded merged-PR cleanup — v0.2.0`.

## Branching and versions

- This is an established `master`-branch solo repo. When the user says commit,
  commit directly to `master`; do not add feature-branch or PR ceremony.
- PIHTI CAD remains an unversioned engineering archive. Only the installable
  `pihti-dedup` tool carries a version.
- Keep `pyproject.toml` and `src/pihti_dedup/__init__.py` synchronized;
  `tests/test_version.py` enforces the contract.
- Bump minor for a user-visible capability, patch for a fix or polish, and do
  not bump for docs, tests, or refactors alone.
- Record every bump newest-first in `.agents/CHANGELOG.md` in the same commit.
- Git tags are the user's call only; agents neither create nor suggest them.

## PIHTI repo notes

- This is an Autodesk Inventor workspace. Be careful with generated caches, lock files, and `OldVersions/`.
- Do not commit `_site/`; it is the MkDocs build output.
- Do commit durable docs and intentionally curated CAD/source files.
- When docs nav changes, run a MkDocs build before committing if the local environment is available.
