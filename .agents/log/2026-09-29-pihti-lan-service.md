# PIHTI viewer LAN service

**Goal:** Let the existing `lab pihti` viewer be started for LAN access through
lab-cli without making LAN reach the default.

## Decisions

- Added `lan_args = ["--host", "0.0.0.0"]` to the existing
  `[services.pihti]` table. The ordinary start remains loopback-only; the Helm
  reach control or `lab start --lan pihti` selects the LAN form.
- Followed Fleet's ship-owned service-registration protocol: only
  `services.toml` was staged in lab-cli, no lab-cli version was bumped, and a
  note was posted to `code/lab-cli`.

## Changed

- `C:/Users/queezz/Dropbox/20-Code/lab-cli/services.toml`
- lab-cli commit `fd2f320` (`Register the pihti service`)
- Fleet note `20260929-6077f59d-59295a`

## Verification

- lab-cli: 286 unit tests passed; Ruff passed; `git diff --check` passed.
- Scratch `lab start --lan pihti --port 4199` used isolated `LAB_*`, PIHTI
  cache, and STEP-mirror paths outside Dropbox.
- The scratch server listened on `0.0.0.0:4199` and `/catalog` returned HTTP
  200. The process was stopped, its process was gone, and port 4199 was free.
- The owner's normal port 4185 and runtime were not touched.

## Next

- Start the viewer with LAN selected in Helm, or run
  `lab start --lan pihti`. Ordinary `lab pihti` remains local-only.

## Usage

- Provider: OpenAI; agent: Codex GPT-5; child-agent count: 0; provider usage:
  unavailable.
