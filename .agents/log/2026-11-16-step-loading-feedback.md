# Show STEP viewer loading and failure states

- Goal: make a slow or interrupted load distinguishable from an idle viewport.
- Add indeterminate progress, elapsed time, preparation/download/render messages,
  and an in-place Retry for the same source. Bound the wait without changing
  the server's preparation limits.
- Changed STEP viewer markup, CSS and JavaScript, version pair and changelog.
  No CAD or drawing group changes.
- Verification: JavaScript syntax, Ruff, whitespace, STEP route tests and
  browser checks of interrupted load and retry against the live vessel.
- Next: use Retry for interrupted connections; a server error retains its
  specific cause in the viewport.
