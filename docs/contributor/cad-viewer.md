# Local CAD viewer and submission checks

Run the viewer from your own Windows checkout. It uses your local CAD files and
Inventor installation; you do not need the lab's launcher or access to another
person's server.

## First setup

1. Clone the repository and install Python 3.12 or newer if it is not installed.
2. Double-click `Setup-PIHTI-Viewer.cmd` in the repository root.
3. If asked, enter the full path of the installed `python.exe`. Use the real
   executable, not the WindowsApps alias. Existing users of `pihti-dedup` are not
   asked again.

Setup creates or refreshes `%USERPROFILE%\.venvs\pihti-dedup`, outside the
checkout, and installs the viewer and its optional geometry/Inventor dependencies.
It requires internet access for the first installation. It does not install
Inventor or change Windows execution policy. Rerun setup after pulling tool updates.

## Open the viewer

Double-click `Start-PIHTI-Viewer.cmd`. Your browser opens the local Catalog at
`http://127.0.0.1:4185/catalog`. Leave the console open while using the viewer;
press Ctrl+C in that console to stop it. If port 4185 is already occupied, use
the command below with another port rather than stopping an unknown process.

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup serve . --open --port 4186
```

The viewer can browse the archive without Inventor. Native reference checks and
Inventor repairs need your installed Inventor running with `PIHTI.ipj` active.
The launcher is local-only; it does not expose a shared network server. Existing
lab users can continue to use `lab pihti`.

## Check your submission before a PR

1. Start Inventor and activate `PIHTI.ipj` from this checkout.
2. Save and close the documents being checked. The check uses their saved state;
   it refuses to certify documents already open in Inventor.
3. Double-click `Check-PIHTI-Submission.cmd` and enter your workspace-relative
   folder, for example `BoronProbe_2026` or your new subsystem folder.
4. Attach `%TEMP%\PIHTI-submission-report.md` to your PR or copy its checklist
   into the PR description. The adjacent JSON is the portable evidence.

The report uses native direct descriptors for every IAM, IDW and IPN in the
selected folder. It lists missing files and resolved dependencies outside the
checkout, without disclosing machine paths. It does not inspect the contents of
outside library files or certify geometry, revisions or intentional suppression.
List external Content Center/library requirements in the PR. Static old-name
strings do not become missing-file requests. No references are changed or CAD saved.

The two TEMP report files are replaced by each run, so attach/copy a report you
want to retain before checking another folder. For named report outputs:

```powershell
& "$HOME\.venvs\pihti-dedup\Scripts\python.exe" -m pihti_dedup submission-report . --folder BoronProbe_2026 --markdown submission-check.md --json submission-check.json
```

On macOS/Linux, use the external environment's `~/.venvs/pihti-dedup/bin/python`
for the local viewer. Native checks require Windows with Inventor.

## Respond to a missing-file issue

Provide the exact requested files in a corrective PR or a Pack-and-Go ZIP attached
to the issue. Include dependent files, not just a top-level IAM or screenshot.
For a rename, fix and save the referring assemblies/drawings in Inventor and
explain the old-to-new mapping. Rerun the check and link the corrective PR.

The reviewer verifies the supplied package in the receiving checkout before
closing the issue. A merge copies tracked files; it does not collect files named
inside Inventor documents. Use the repository's missing-dependency issue and PR
templates to keep the request, delivery and verification in one place.
