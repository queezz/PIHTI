# Campus PC check — does the Inventor process work there?

A 15-minute handout for the second workstation (Inventor 2027 expected). Each
step has one command and one thing to look at. Paste the outputs, or a photo
of them, back into the session; the last section says what to paste.

Nothing here changes CAD. Step 6 writes one STEP file into the mirror and
nothing else.

## 0. What must be true first

- Dropbox has finished syncing `Drawings\PIHTI` and the sibling
  `Drawings\PIHTI-step` (the STEP mirror, about 900 files). Wait for the green
  tick before step 4.
- A Python 3.12 or newer is installed. Check:

```powershell
py -0
```

If no 3.12+ appears, install one from python.org (per-user is fine) and come
back.

## 1. Make the tool's environment (once per machine)

Never inside Dropbox. Same location as at home, so the commands match:

```powershell
py -3.12 -m venv "$HOME\.venvs\pihti-dedup"
```

```powershell
Set-Location "$HOME\Dropbox\Drawings\PIHTI"; & "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pip install -e ".[dev,preview,step,inventor]"
```

Look at: the last line says `Successfully installed ... pihti-dedup-0.2x.x`.
The `step` extra builds nothing (cascadio ships a wheel); if pip fails, paste
the last 20 lines.

## 2. Tests, no Inventor involved

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pytest -q -p no:cacheprovider --basetemp "$env:LOCALAPPDATA\Temp\pihti-dedup-pytest-$(Get-Random)"
```

Look at: the last line, `NNN passed` and maybe some `skipped`. A `failed`
means the machine differs in a way we want to know; paste the failing names.

## 3. Viewer without Inventor

There is no `lab pihti` alias on this machine; start it directly:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup serve "$HOME\Dropbox\Drawings\PIHTI" --port 4185 --open
```

Look at, in the browser:

- Catalog shows folders with covers and the file tiles with thumbnails
  (thumbnails render on first visit; the first folder takes a few seconds).
- Hover `bellows\bellows_flange.ipt`: the inspector turns it in 3D, Y up. If
  it stays a still with "3D needs the STEP mirror", Dropbox has not brought
  `PIHTI-step` yet.
- Top bar: `STEP mirror 905 / 908` or close to it.
- STEP mirror tab: the Inventor line says Inventor is not running. Expected
  at this point.

Leave the viewer running for the rest.

## 4. Inventor session detection

Start Inventor 2027, open `PIHTI.ipj` as the project, no documents. Then:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup step-mirror status "$HOME\Dropbox\Drawings\PIHTI"
```

Look at: counts current / stale / missing / need Doctor, close to home's
(905 / 0 / 3 / 2 on 2026-09-25). Then reload the STEP mirror page: its
Inventor line should now say `Inventor 2027.x is running`. Step 6 prints the
version on the command line too.

If it says Inventor is not running while it is: the COM registration on
this machine differs. Paste the output of

```powershell
Get-ItemProperty "Registry::HKEY_CLASSES_ROOT\Inventor.Application\CLSID"
```

## 5. Export one STEP through Inventor

Re-exports a small part that already has a copy; harmless:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup step-mirror export "$HOME\Dropbox\Drawings\PIHTI" "bellows/rail.ipt" --force
```

Look at: `exported` with a time under a second, and no dialog in Inventor. A
dialog that stays open, or `not answering`, is the finding.

## 6. Rename repair, dry run only

Shows the plan and touches nothing:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup rename "bellows/rail.ipt" "rail-check.ipt" "$HOME\Dropbox\Drawings\PIHTI" --repair --dry
```

Look at: `inventor: 2027.1` (or whatever is installed), then
`bellows\bellows.iam: will repoint 1 reference`, then `DRY RUN: nothing
renamed or saved`. A warning that `rail.ipt` still exists under `staging\`
is expected. Do not run it without `--dry`.

## 7. Stop

Close the viewer window's PowerShell with Ctrl+C. Close Inventor. The
machine-local cache lives in `%LOCALAPPDATA%\pihti-dedup\`; leave it.

## What to paste back

1. Step 1: the `Successfully installed` line or the failure.
2. Step 2: the last pytest line.
3. Step 4: the status output.
4. Step 5: the export line.
5. Anything that looked different from home: a dialog, a missing thumbnail
   set, a wrong count in the top bar.

Known differences to expect, not findings: the cache root is rebuilt on
this machine (first thumbnails are slow), the mirror count may lag Dropbox,
and `lab pihti` does not exist here.
