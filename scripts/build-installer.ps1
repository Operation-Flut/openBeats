[CmdletBinding()]
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$installerScript = Join-Path $projectRoot "installer\OpenBeats.iss"

& (Join-Path $PSScriptRoot "build.ps1") -Python $Python
if ($LASTEXITCODE -ne 0) {
    throw "OpenBeats application build failed with exit code $LASTEXITCODE"
}

$iscc = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
if ($iscc) {
    $isccPath = $iscc.Source
} else {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )
    $isccPath = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
}

if (-not $isccPath) {
    throw "Inno Setup 6 was not found. Install it, then rerun scripts\build-installer.ps1."
}

Write-Host "Compiling OpenBeats installer with $isccPath..."
& $isccPath $installerScript
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

$outputDir = Join-Path $projectRoot "installer\output"
$installer = Get-ChildItem -LiteralPath $outputDir -Filter "OpenBeatsSetup-*-dev-x64.exe" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if (-not $installer) {
    throw "Inno Setup completed but no OpenBeats installer was found in $outputDir."
}

Write-Host "OpenBeats installer created: $($installer.FullName)"
