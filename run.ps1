$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Requirements = Join-Path $Root "requirements.txt"
$InstalledMarker = Join-Path $Root ".venv\.requirements.installed"

Set-Location $Root

if (-not (Test-Path $VenvPython)) {
    python -m venv .venv
}

$NeedsInstall = -not (Test-Path $InstalledMarker)
if (-not $NeedsInstall) {
    $NeedsInstall = (Get-Item $Requirements).LastWriteTimeUtc -gt (Get-Item $InstalledMarker).LastWriteTimeUtc
}

if ($NeedsInstall) {
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r $Requirements
    Copy-Item $Requirements $InstalledMarker -Force
}

& $VenvPython -m streamlit run app.py
