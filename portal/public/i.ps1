# laya-npu bootstrap for Windows.
#
#   irm https://laya.manef.dev/i.ps1 | iex
#
# Downloads the source, then hands off to the real installer in it. Nothing is
# installed from here: install.ps1 owns Python, OpenVINO, the model and the UI.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Target = Join-Path $env:USERPROFILE "laya-npu"
$Zip    = Join-Path $env:TEMP "laya-npu-main.zip"
$Url    = "https://github.com/rahmanef63/laya-npu/archive/refs/heads/main.zip"

Write-Host "`nlaya-npu" -ForegroundColor White
Write-Host "typed decisions on the Intel NPU`n" -ForegroundColor DarkGray

if (Test-Path (Join-Path $Target "install.ps1")) {
    Write-Host "  found existing copy at $Target" -ForegroundColor DarkGray
    Write-Host "  running its installer (keeps your .env)`n" -ForegroundColor DarkGray
    & (Join-Path $Target "install.ps1")
    return
}

Write-Host "  downloading source..." -ForegroundColor DarkGray
Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing

$Stage = Join-Path $env:TEMP "laya-npu-stage"
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
Expand-Archive -Path $Zip -DestinationPath $Stage -Force
Remove-Item $Zip -Force

$Src = Get-ChildItem $Stage -Directory | Select-Object -First 1
if (-not $Src) { throw "the archive did not contain a directory" }

# Move rather than copy so a large tree is not duplicated on the same disk.
Move-Item -Path $Src.FullName -Destination $Target
Remove-Item $Stage -Recurse -Force

Write-Host "  source at $Target`n" -ForegroundColor DarkGray
& (Join-Path $Target "install.ps1")
