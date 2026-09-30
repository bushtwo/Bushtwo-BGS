@echo off
cd /d "%~dp0"

:: Check if pythonw is available to run silently without console
where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pythonw "main.py"
    exit
)

:: Fallback to python
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" python "main.py"
    exit
)

echo [Error] Python was not found in your system PATH.
echo Please make sure Python is installed.
pause
