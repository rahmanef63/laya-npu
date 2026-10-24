# One-click install for laya-npu (Windows, has the NPU).
#
# Idempotent: run it again and it skips what is done.
#
#   .\install.ps1

param(
    # Optional. Downloads and runs Intel's NPU driver installer. Needs administrator.
    # Off by default: a driver update is a deliberate act, and on an OEM laptop the
    # vendor build is usually the tested one.
    [switch]$InstallDriver
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Model   = Join-Path $env:USERPROFILE "models\laya-ov-int8"
$PyUrl   = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
$PyMin   = [version]"3.10"
$MaxLen  = 256
$WebPort = 8649
$Portal  = "https://laya.manef.dev"
$Whisper = Join-Path $env:USERPROFILE "models\whisper-base-int8"
$Markers = 8

function Say($m)  { Write-Host "  $m" }
function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  ok  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  !!  $m" -ForegroundColor Yellow }

Write-Host "`nlaya-npu installer" -ForegroundColor White
Write-Host "typed decisions on Intel NPU`n" -ForegroundColor DarkGray

# ---------------------------------------------------------------- python
Step "Python"

function Find-Python {
    foreach ($c in @("python", "python3", "py")) {
        $exe = Get-Command $c -ErrorAction SilentlyContinue
        if (-not $exe) { continue }
        try {
            $v = & $exe.Source -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
            if ([version]$v -ge $PyMin) { return $exe.Source }
        } catch { }
    }
    # the Microsoft Store stub answers but has no pip: skip anything under WindowsApps
    foreach ($p in @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\Python312\python.exe"
    )) { if (Test-Path $p) { return $p } }
    return $null
}

$python = Find-Python
if ($python -and $python -like "*WindowsApps*") { $python = $null }

if (-not $python) {
    Say "Python >= 3.10 not found, installing 3.12 (silent, ~2 min)"
    $exe = Join-Path $env:TEMP "python-install.exe"
    if (-not (Test-Path $exe)) { Invoke-WebRequest $PyUrl -OutFile $exe }
    Start-Process -FilePath $exe -Wait -ArgumentList @(
        "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_pip=1"
    )
    $python = Find-Python
    if (-not $python) { throw "Python install failed. Install manually from python.org and re-run." }
    Ok "installed $python"
} else {
    Ok "found $python"
}

# ---------------------------------------------------------------- packages
Step "Packages"

function Py([string[]]$PyArgs) { & $python @PyArgs }

Py @("-m", "pip", "install", "--quiet", "--upgrade", "pip") | Out-Null

$needLaya = $true
try { Py @("-c", "import laya, openvino; print(1)") | Out-Null; $needLaya = $false } catch { }
if ($needLaya) {
    Say "installing openvino + laya-openvino (~250 MB)"
    Py @("-m", "pip", "install", "--quiet", "openvino>=2026.0", "openvino-tokenizers",
          "openvino-genai", "huggingface_hub", "transformers", "numpy", "torch",
          "--extra-index-url", "https://download.pytorch.org/whl/cpu") | Out-Null
    Py @("-m", "pip", "install", "--quiet",
          "git+https://github.com/rupeshs/laya-openvino.git") | Out-Null
    Ok "packages installed"
} else {
    Ok "already installed"
}

# ---------------------------------------------------------------- model
Step "Model"

$xml = Join-Path $Model "openvino_model.xml"
if (Test-Path $xml) {
    Ok "model present ($Model)"
} else {
    Say "downloading rupeshs/laya-ov-int8 (405 MB)"
    $py = @"
from huggingface_hub import snapshot_download
snapshot_download('rupeshs/laya-ov-int8', local_dir=r'$Model')
print('done')
"@
    $tmp = Join-Path $env:TEMP "laya-dl.py"
    Set-Content -Path $tmp -Value $py -Encoding UTF8
    Py @($tmp)
    if (-not (Test-Path $xml)) { throw "model download failed" }
    Ok "downloaded"
}

# ---------------------------------------------------------------- static IR
Step "Static IR (NPU needs fixed shapes)"

$static = Join-Path $Model "openvino_model_static.xml"
if (Test-Path $static) {
    Ok "already static"
} else {
    $py = @"
import openvino as ov, numpy as np, os
d = r'$Model'
core = ov.Core()
m = core.read_model(os.path.join(d, 'openvino_model.xml'))
shapes = {}
for i in m.inputs:
    n = i.get_any_name()
    shapes[n] = [1, $Markers] if n.startswith('marker') else [1, $MaxLen]
shapes['qtype'] = [1]
m.reshape({i.get_any_name(): shapes[i.get_any_name()] for i in m.inputs})
ov.save_model(m, os.path.join(d, 'openvino_model_static.xml'))
print('static ok')
"@
    $tmp = Join-Path $env:TEMP "laya-static.py"
    Set-Content -Path $tmp -Value $py -Encoding UTF8
    Py @($tmp)
    if (-not (Test-Path $static)) { throw "could not build static IR" }
    Ok "static IR built"
}

# ---------------------------------------------------------------- NPU driver
Step "NPU driver"

$drvPy = Join-Path $env:TEMP "laya-driver.py"
$drvCode = @"
import json, sys
sys.path.insert(0, r'$Root\server')
import npu_driver
print('LAYA_DRIVER ' + json.dumps(npu_driver.check()))
"@
Set-Content -Path $drvPy -Value $drvCode -Encoding UTF8

$drv = $null
try {
    $raw = Py @($drvPy) 2>&1
    $line = $raw | Where-Object { "$_" -like "*LAYA_DRIVER *" } | Select-Object -Last 1
    if ($line) {
        $json = ("$line" -replace '^.*LAYA_DRIVER ', '')
        $drv = $json | ConvertFrom-Json
    } else {
        Warn "driver check produced no output"
        ($raw | Select-Object -Last 2) | ForEach-Object { Say "$_" }
    }
} catch {
    Warn "could not read NPU driver state: $_"
}

if ($drv) {
    if (-not $drv.present) {
        Warn "no Intel NPU detected - the app will use GPU or CPU"
    } else {
        Say "installed: $($drv.current) ($($drv.date))"
        if ($drv.latest) { Say "latest:    $($drv.latest)" }

        if ($drv.action -eq "update") {
            Warn "driver update available: $($drv.current) -> $($drv.latest)"
            if ($drv.known_bad) {
                Warn "this version is known to crash OpenVINO on Panther Lake"
            }
            Say "download: $($drv.url)"

            if ($InstallDriver) {
                Say "downloading the Intel installer (needs administrator, will reboot)"
                try {
                    $page = Invoke-WebRequest -Uri $drv.url -UseBasicParsing -TimeoutSec 30
                    $exeLink = ($page.Links |
                        Where-Object { $_.href -match '\.exe$' -and $_.href -match 'npu' } |
                        Select-Object -First 1).href
                    if (-not $exeLink) { throw "direct .exe link not found on the Intel page" }
                    if ($exeLink -notmatch '^https?://') { $exeLink = "https://www.intel.com$exeLink" }
                    $out = Join-Path $env:TEMP "npu-driver-setup.exe"
                    Say "downloading $exeLink"
                    Invoke-WebRequest -Uri $exeLink -OutFile $out -UseBasicParsing -TimeoutSec 300
                    Say "running silently - approve the UAC prompt"
                    Start-Process -FilePath $out -ArgumentList "/s" -Verb RunAs -Wait
                    Ok "driver installer finished; reboot before the NPU will use it"
                } catch {
                    Warn "automatic driver install failed: $_"
                    Warn "install manually from: $($drv.url)"
                }
            } else {
                Say "run .\install.ps1 -InstallDriver to update it automatically"
            }
        } elseif ($drv.action -eq "recommended") {
            Warn "driver $($drv.current) is older than the recommended $($drv.latest) but not known-bad"
            Say "upgrade later from: $($drv.url)"
        } else {
            Ok "driver is current"
        }
    }
}

# ---------------------------------------------------------------- verify devices
Step "Verify devices"

$py = @"
import openvino as ov, os, json
core = ov.Core()
d = r'$Model'
m = core.read_model(os.path.join(d, 'openvino_model_static.xml'))
out = {}
for dev in ('NPU', 'GPU', 'CPU'):
    if dev not in core.available_devices:
        out[dev] = 'absent'
        continue
    try:
        core.compile_model(m, dev)
        out[dev] = 'ok'
    except Exception as e:
        out[dev] = 'fail: ' + str(e)[:80]
print(json.dumps(out))
"@
$tmp = Join-Path $env:TEMP "laya-verify.py"
Set-Content -Path $tmp -Value $py -Encoding UTF8
try {
    $result = Py @($tmp) | Select-Object -Last 1
    Say $result
    if ($result -notmatch '"CPU": "ok"') {
        Warn "CPU compile failed - the app will have no working backend"
    }
} catch {
    Warn "device verification failed: $_"
}

# ---------------------------------------------------------------- web
Step "Web UI"

$dist = Join-Path $Root "web\dist\index.html"
if (Test-Path $dist) {
    Ok "already built"
} elseif (Test-Path (Join-Path $Root "src\routes\+page.svelte")) {
    # A source checkout needs a build. Fall through to npm below.
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        Warn "npm not found - skipping UI build"
        Warn "install Node.js 20+ then run: npm install; npm run build"
    } else {
        Say "installing frontend deps"
        Push-Location $Root
        try {
            & $npm.Source install --silent
            if ($LASTEXITCODE -ne 0) { Warn "npm install exited $LASTEXITCODE" }
            & $npm.Source run build
            if ($LASTEXITCODE -ne 0) {
                Warn "npm run build exited $LASTEXITCODE - the UI will be missing"
                Warn "this is usually a stale node_modules or a native binding mismatch;"
                Warn "delete node_modules and rerun, or run: npm install ; npm run build"
            }
        } catch {
            Warn "frontend build failed: $_"
        } finally { Pop-Location }
        if (Test-Path $dist) {
            Ok "built"
        } else {
            Warn "the UI did not build. The API still works, but there is no page."
            Warn "fix it with:  npm install ; npm run build"
        }
    }
}

# ---------------------------------------------------------------- shortcuts
Step "Shortcuts"

try {
    & (Join-Path $Root "shortcut.ps1") -Quiet
    $desktop = [Environment]::GetFolderPath("Desktop")
    if (Test-Path (Join-Path $desktop "laya-npu.lnk")) {
        Ok "desktop shortcut"
    } else {
        Warn "desktop shortcut not created"
    }
} catch {
    Warn "shortcut creation failed: $_"
}

# ---------------------------------------------------------------- config
Step "Config"

$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
    # Windows PowerShell 5.1 has no utf8NoBOM encoding and Set-Content -Encoding UTF8
    # writes a BOM that corrupts the first variable name, so write bytes directly.
    $lines = @(
        "LAYA_MODEL=$Model",
        "LAYA_DEVICE=NPU",
        "LAYA_MAXLEN=$MaxLen",
        "LAYA_MARKERS=$Markers",
        "WEB_PORT=$WebPort",
        "LAYA_PORTAL=$Portal",
        "WHISPER_MODEL=$Whisper"
    )
    [System.IO.File]::WriteAllLines($envFile, $lines, (New-Object System.Text.UTF8Encoding($false)))
    Ok "wrote .env"
} else {
    Ok ".env exists"
}

Write-Host "`nDone." -ForegroundColor Green
Write-Host "Double-click the laya-npu shortcut on your Desktop," -ForegroundColor White
Write-Host "or run:  .\start.ps1" -ForegroundColor White
Write-Host "Then open:      http://localhost:$WebPort`n" -ForegroundColor White
