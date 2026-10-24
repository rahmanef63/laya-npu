# Create desktop and Start Menu shortcuts for laya-npu.
#
# Called by install.ps1. Also usable on its own after moving the folder:
#   .\shortcut.ps1

param([switch]$Quiet)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Target = Join-Path $Root "laya-npu.cmd"

if (-not (Test-Path $Target)) {
    Write-Host "laya-npu.cmd missing next to shortcut.ps1" -ForegroundColor Red
    exit 1
}

# Icon: reuse the icon from the Python launcher if one is available, so the
# shortcut is not a blank page. Falls back to the default console icon.
$Icon = $null
foreach ($p in @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
)) { if (Test-Path $p) { $Icon = "$p,0"; break } }

$shell = New-Object -ComObject WScript.Shell

function New-Shortcut($path, $description) {
    $sc = $shell.CreateShortcut($path)
    $sc.TargetPath = $Target
    $sc.WorkingDirectory = $Root
    $sc.Description = $description
    $sc.WindowStyle = 7                 # minimised: the UI opens in the browser
    if ($Icon) { $sc.IconLocation = $Icon }
    $sc.Save()
}

$made = @()

$desktop = [Environment]::GetFolderPath("Desktop")
if ($desktop -and (Test-Path $desktop)) {
    $p = Join-Path $desktop "laya-npu.lnk"
    New-Shortcut $p "Typed decisions on Intel NPU"
    $made += $p
}

$start = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
if (Test-Path $start) {
    $p = Join-Path $start "laya-npu.lnk"
    New-Shortcut $p "Typed decisions on Intel NPU"
    $made += $p
}

if (-not $Quiet) {
    if ($made.Count) {
        Write-Host "  ok  shortcuts created:" -ForegroundColor Green
        $made | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
    } else {
        Write-Host "  !!  could not create shortcuts (no Desktop or Start Menu folder)" -ForegroundColor Yellow
    }
}
