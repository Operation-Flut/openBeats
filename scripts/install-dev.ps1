param(
    [switch]$StartAgent
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LuaSource = Join-Path $Root "resolve\OpenBeats.lua"

if (-not (Test-Path $LuaSource)) {
    throw "OpenBeats.lua not found at $LuaSource"
}

Write-Host "Installing OpenBeats Python package..."
python -m pip install -e "$Root"

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
    Start-Process -FilePath "python" -ArgumentList "-m", "openbeats.agent" -WindowStyle Hidden
}

Write-Host "OpenBeats development install complete. Restart DaVinci Resolve before testing."
Write-Host "Run 'openbeats-agent' in a terminal if the agent is not already running."
