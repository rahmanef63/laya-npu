@echo off
REM Double-click entry point for laya-npu.
REM Keeps the window open on failure so the error is readable.
setlocal
cd /d "%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell not found. Run install.ps1 manually.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
if errorlevel 1 (
  echo.
  echo laya-npu exited with an error. Log above.
  pause
)
endlocal
