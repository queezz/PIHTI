# Inventor reference recheck (pihti-dedup 0.29.1)

**Goal:** Unblock an assembly the owner already repaired in Inventor when the
old filename remains only as an inert byte string in the IAM.

## Decisions

- The static byte scan remains conservative; it is never silently overruled.
- A missing-reference row offers **Recheck Inventor** only while Inventor is
  running. Inventor opens the assembly with unresolved dialogs suppressed.
- A verification is recorded only when the direct descriptor count for that
  exact filename is zero, and it suppresses only that assembly/name pair.
- Verified pairs live in `.agents/reference-verifications.jsonl`, separate
  from actual file renames.

## Changed paths

- `src/pihti_dedup/inventor_session.py`, `renames.py`, `web.py`, `cli.py`
- `src/pihti_dedup/templates/step_mirror.html`
- `tests/test_step_mirror.py`
- `README.md`, `pyproject.toml`, `src/pihti_dedup/__init__.py`
- `.agents/CHANGELOG.md`

## Verification

- Live Inventor 2027.1 check of
  `ElectronicsBox/Win-GPIO-Box/cosel-psu-din-clip.iam`: zero direct
  `manometer-bracket.ipt` descriptors.
- Focused route regression: 1 passed. Full suite: 499 passed. Ruff,
  `git diff --check`, and strict MkDocs build passed.

## Usage

- Provider: OpenAI; agent: Codex GPT-5; child-agent count: 0; provider usage:
  unavailable.
