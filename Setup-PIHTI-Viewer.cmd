@echo off
setlocal
set "viewerPython=%USERPROFILE%\.venvs\pihti-dedup\Scripts\python.exe"
if exist "%viewerPython%" goto install
echo Enter the full path to an installed Python 3.12 or newer python.exe.
echo Use the actual executable, not the WindowsApps alias.
set /p "viewerPython=Python executable: "
set "viewerPython=%viewerPython:"=%"
if not exist "%viewerPython%" goto missing
:install
"%viewerPython%" "%~dp0scripts\setup_viewer.py"
set "viewerResult=%ERRORLEVEL%"
pause
exit /b %viewerResult%
:missing
echo Python executable not found. Install Python 3.12 or newer, then try again.
pause
exit /b 2
