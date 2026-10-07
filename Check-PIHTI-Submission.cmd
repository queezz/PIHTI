@echo off
setlocal
set "viewerPython=%USERPROFILE%\.venvs\pihti-dedup\Scripts\python.exe"
if not exist "%viewerPython%" goto missing
echo Start Inventor, open PIHTI.ipj, and close the documents you want to check.
"%viewerPython%" -m pihti_dedup submission-report "%~dp0." --markdown "%TEMP%\PIHTI-submission-report.md" --json "%TEMP%\PIHTI-submission-report.json"
set "viewerResult=%ERRORLEVEL%"
echo Report: %TEMP%\PIHTI-submission-report.md
echo Attach the report to the submission PR or missing-dependency issue.
pause
exit /b %viewerResult%
:missing
echo Run Setup-PIHTI-Viewer.cmd once, then reopen this checker.
pause
exit /b 2
