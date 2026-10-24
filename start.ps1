# Start laya-npu and open the UI.
#
#   .\start.ps1            # serve and open the browser
#   .\start.ps1 -NoOpen    # serve only
#   .\start.ps1 -Foreground  # keep the console visible (default when run directly)

param(
    [switch]$NoOpen,
    [switch]$StayOpen
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 8649

$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "Not installed yet." -ForegroundColor Yellow
    Write-Host "Run install.ps1 first, or double-click install.cmd." -ForegroundColor DarkGray
    if ($StayOpen) { Read-Host "`nPress Enter to close" }
    exit 1
}

# -Encoding utf8 strips a BOM written by older installs, which otherwise corrupts
# the first variable name.
Get-Content $envFile -Encoding utf8 | ForEach-Object {
    if ($_ -match "^\s*(?:\ufeff)?([A-Z_]+)\s*=\s*(.*)$") {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim(), "Process")
    }
}
if ($env:WEB_PORT) { $Port = [int]$env:WEB_PORT }

$python = $null
foreach ($p in @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "C:\Python312\python.exe"
)) { if (Test-Path $p) { $python = $p; break } }
if (-not $python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") { $python = $cmd.Source }
}
if (-not $python) {
    Write-Host "Python not found. Run install.ps1" -ForegroundColor Red
    if ($StayOpen) { Read-Host "`nPress Enter to close" }
    exit 1
}

# Already running? Just open the browser.
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    Write-Host "laya-npu already running on http://localhost:$Port" -ForegroundColor Green
    if (-not $NoOpen) { Start-Process "http://localhost:$Port" }
    Start-Sleep -Seconds 2
    exit 0
}

$url = "http://localhost:$Port"

if (-not $NoOpen) {
    # Poll until the server answers, then open. Runs as a detached process so it
    # cannot be killed when this script's job table is cleaned up.
    $opener = @"
`$url = '$url'
for (`$i = 0; `$i -lt 120; `$i++) {
    Start-Sleep -Seconds 2
    try {
        `$r = Invoke-WebRequest `$url -TimeoutSec 2 -UseBasicParsing
        if (`$r.StatusCode -eq 200) { Start-Process `$url; break }
    } catch { }
}
"@
    $tmp = Join-Path $env:TEMP "laya-open.ps1"
    Set-Content -Path $tmp -Value $opener -Encoding UTF8
    Start-Process -FilePath "powershell" `
        -ArgumentList @("-NoProfile", "-WindowStyle", "Hidden", "-File", $tmp) `
        -WindowStyle Hidden | Out-Null
    Write-Host "Opening $url when ready..." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  laya-npu" -ForegroundColor White
Write-Host "  http://localhost:$Port" -ForegroundColor DarkGray
Write-Host "  first NPU compile takes 30-90s." -ForegroundColor DarkGray
Write-Host "  Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

Push-Location $Root
try {
    & $python "server\web.py"
} catch {
    Write-Host "`nServer error: $_" -ForegroundColor Red
    if ($StayOpen) { Read-Host "Press Enter to close" }
    exit 1
} finally {
    Pop-Location
}
