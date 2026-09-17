[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$installerScript = Join-Path $projectRoot "installer\OpenBeats.iss"
$pyprojectPath = Join-Path $projectRoot "pyproject.toml"

if ([string]::IsNullOrWhiteSpace($Version)) {
    $pyproject = Get-Content -LiteralPath $pyprojectPath -Raw
    $match = [regex]::Match($pyproject, '(?m)^version\s*=\s*"([^"]+)"')
    if (-not $match.Success) {
        throw "Could not determine OpenBeats version from pyproject.toml."
    }
    $Version = $match.Groups[1].Value
}

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "OpenBeats installer version must use MAJOR.MINOR.PATCH format. Got: $Version"
}

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

Write-Host "Compiling OpenBeats $Version installer with $isccPath..."
& $isccPath "/DMyAppVersion=$Version" $installerScript
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

$outputDir = Join-Path $projectRoot "installer\output"
$expectedName = "OpenBeatsSetup-$Version-x64.exe"
$installer = Join-Path $outputDir $expectedName
if (-not (Test-Path -LiteralPath $installer)) {
    throw "Inno Setup completed but $expectedName was not found in $outputDir."
}

Write-Host "OpenBeats installer created: $installer"
