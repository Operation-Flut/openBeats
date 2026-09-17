param(
    [switch]$StartAgent,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LuaSource = Join-Path $Root "resolve\OpenBeats.lua"
$VenvPath = Join-Path $Root ".venv-dev"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

function Invoke-Native([string]$FilePath, [string[]]$Arguments) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path $LuaSource)) {
    throw "OpenBeats.lua not found at $LuaSource"
}

$pythonCommand = Get-Command $Python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    throw "Python was not found. Install Python 3.11 or newer, then rerun this script."
}

& $Python -c "import sys; print(sys.version); raise SystemExit(0 if sys.version_info >= (3, 11) else 42)"
if ($LASTEXITCODE -ne 0) {
    throw "OpenBeats requires Python 3.11 or newer. Your '$Python' command points to an older Python installation."
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating OpenBeats development environment at $VenvPath..."
    Invoke-Native $Python @("-m", "venv", $VenvPath)
}

Write-Host "Updating pip in the OpenBeats development environment..."
Invoke-Native $VenvPython @("-m", "pip", "install", "--upgrade", "pip")

Write-Host "Installing OpenBeats Python package..."
Invoke-Native $VenvPython @("-m", "pip", "install", "-e", $Root)

$scriptDirs = @(
    (Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"),
    (Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility")
)

foreach ($dir in $scriptDirs) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Copy-Item -Path $LuaSource -Destination (Join-Path $dir "OpenBeats.lua") -Force
    Write-Host "Installed Resolve script: $dir\OpenBeats.lua"
}

$localRoot = Join-Path $env:LOCALAPPDATA "OpenBeats"
New-Item -ItemType Directory -Path (Join-Path $localRoot "Exchange") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $localRoot "Sessions") -Force | Out-Null

if ($StartAgent) {
    Write-Host "Starting OpenBeats agent..."
    Start-Process -FilePath $VenvPython -ArgumentList "-m", "openbeats.agent" -WindowStyle Hidden
}

Write-Host "OpenBeats development install complete. Restart DaVinci Resolve before testing."
Write-Host "Agent command: $VenvPython -m openbeats.agent"
