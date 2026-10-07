@echo off
setlocal
set "viewerPython=%USERPROFILE%\.venvs\pihti-dedup\Scripts\python.exe"
if not exist "%viewerPython%" goto missing
"%viewerPython%" -m pihti_dedup serve "%~dp0." --host 127.0.0.1 --port 4185 --open
set "viewerResult=%ERRORLEVEL%"
if not "%viewerResult%"=="0" pause
exit /b %viewerResult%
:missing
echo Run Setup-PIHTI-Viewer.cmd once, then reopen this launcher.
pause
exit /b 2
