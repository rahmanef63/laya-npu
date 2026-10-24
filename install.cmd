@echo off
REM Double-click entry point for the installer.
REM Keeps the window open so you can read the result.
setlocal
cd /d "%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell not found.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
set RC=%ERRORLEVEL%

echo.
if %RC% neq 0 (
  echo Install failed with code %RC%. Scroll up for the reason.
) else (
  echo Done. Double-click the laya-npu icon on your Desktop to start.
)
pause
endlocal
exit /b %RC%
