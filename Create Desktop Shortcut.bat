@echo off
cd /d "%~dp0"

echo Creating Desktop Shortcut for Bushtwo BGS...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $desktop = [System.Environment]::GetFolderPath('Desktop'); ^
   $shortcutPath = Join-Path $desktop 'Bushtwo BGS.lnk'; ^
   $shortcut = $ws.CreateShortcut($shortcutPath); ^
   $pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source; ^
   if (-not $pythonw) { $pythonw = (Get-Command python.exe).Source }; ^
   $shortcut.TargetPath = $pythonw; ^
   $shortcut.Arguments = '\"' + (Join-Path (Get-Location) 'main.py') + '\"'; ^
   $shortcut.WorkingDirectory = (Get-Location).Path; ^
   $iconPath = Join-Path (Get-Location) 'bushtwo_bgs.ico'; ^
   if (Test-Path $iconPath) { $shortcut.IconLocation = $iconPath }; ^
   $shortcut.Description = 'Bushtwo BGS - Wallpaper Switcher'; ^
   $shortcut.Save(); ^
   Write-Host 'Shortcut created successfully on your Desktop!'"

echo.
pause
