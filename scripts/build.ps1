[CmdletBinding()]
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot ".venv-build"
$distPath = Join-Path $projectRoot "dist"
$distAppPath = Join-Path $distPath "OpenBeats"
$launcher = Join-Path $projectRoot "app\openbeats_launcher.py"

function Stop-OpenBeatsProcessesFromPath([string]$rootPath) {
    if (-not (Test-Path -LiteralPath $rootPath)) { return }
    $root = [System.IO.Path]::GetFullPath($rootPath).TrimEnd('\') + '\'
    foreach ($process in (Get-Process -Name "OpenBeats" -ErrorAction SilentlyContinue)) {
        $processPath = $null
        try { $processPath = $process.Path } catch { continue }
        if (-not $processPath) { continue }
        $fullProcessPath = [System.IO.Path]::GetFullPath($processPath)
        if (-not $fullProcessPath.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        Write-Host "Stopping local build process $($process.Id): $fullProcessPath"
        Stop-Process -Id $process.Id -Force -ErrorAction Stop
        try { $process.WaitForExit(5000) | Out-Null } catch { }
    }
}

function Remove-DirectoryWithRetry([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    $lastError = $null
    for ($attempt = 1; $attempt -le 6; $attempt++) {
        try {
            Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
            return
        } catch {
            $lastError = $_
            if ($attempt -lt 6) { Start-Sleep -Milliseconds (250 * $attempt) }
        }
    }
    throw "Could not remove old build output at $path. Last error: $($lastError.Exception.Message)"
}

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Packaging launcher not found at $launcher"
}

Stop-OpenBeatsProcessesFromPath $distAppPath
Remove-DirectoryWithRetry $distAppPath

Write-Host "Creating isolated Python build environment..."
& $Python -m venv $venvPath --clear
if ($LASTEXITCODE -ne 0) { throw "Creating the build virtual environment failed." }

$pythonExe = Join-Path $venvPath "Scripts\python.exe"
& $pythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Upgrading pip failed." }

& $pythonExe -m pip install -e "${projectRoot}[build]"
if ($LASTEXITCODE -ne 0) { throw "Installing OpenBeats build dependencies failed." }

New-Item -ItemType Directory -Path $distPath -Force | Out-Null

Write-Host "Building OpenBeats.exe..."
& $pythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name OpenBeats `
    --paths (Join-Path $projectRoot "app") `
    --collect-all imageio_ffmpeg `
    --collect-all librosa `
    --collect-all soundfile `
    --collect-all soxr `
    --collect-all numba `
    --hidden-import openbeats.settings_ui `
    --hidden-import kivy_deps.angle `
    --hidden-import kivy_deps.glew `
    --hidden-import kivy_deps.sdl2 `
    --hidden-import llvmlite.binding `
    --copy-metadata imageio-ffmpeg `
    --copy-metadata librosa `
    --distpath $distPath `
    --workpath (Join-Path $projectRoot "build\pyinstaller") `
    $launcher
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$exe = Join-Path $distAppPath "OpenBeats.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "PyInstaller completed but $exe was not created."
}

Write-Host "Running packaged dependency self-test..."
$process = Start-Process -FilePath $exe -ArgumentList "--self-test" -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "Packaged OpenBeats self-test failed with exit code $($process.ExitCode)."
}

Write-Host "OpenBeats Windows bundle created at $distAppPath"
