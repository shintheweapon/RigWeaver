<#
.SYNOPSIS
    Builds the installable zip of the RigWeaver extension.

.DESCRIPTION
    Runs Blender's own extension build on the src folder, writes the zip to the
    dist folder next to this script, and checks that the zip installs cleanly:
    blender_manifest.toml and __init__.py at the top, no __pycache__ folders.
    The zip is named <id>-<version>.zip from src\blender_manifest.toml.

.PARAMETER Blender
    Path to blender.exe (Blender 4.2 or later).

.EXAMPLE
    .\build.ps1

.EXAMPLE
    .\build.ps1 -Blender "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
#>
param(
    [string]$Blender = 'E:\Program Files Portable\blender-4.5.0-windows-x64\blender.exe'
)

$ErrorActionPreference = 'Stop'

$sourceDir = Join-Path $PSScriptRoot 'src'
$distDir = Join-Path $PSScriptRoot 'dist'
$manifestPath = Join-Path $sourceDir 'blender_manifest.toml'

if (-not (Test-Path -LiteralPath $Blender -PathType Leaf)) {
    Write-Host "Blender not found at: $Blender" -ForegroundColor Red
    Write-Host 'Pass its location with -Blender "<path to blender.exe>".'
    exit 1
}

# Expected zip name, from the manifest's id and version
$manifest = Get-Content -LiteralPath $manifestPath -Raw
$id = [regex]::Match($manifest, '(?m)^\s*id\s*=\s*"([^"]+)"').Groups[1].Value
$version = [regex]::Match($manifest, '(?m)^\s*version\s*=\s*"([^"]+)"').Groups[1].Value
if (-not $id -or -not $version) {
    Write-Host "Could not read id and version from $manifestPath" -ForegroundColor Red
    exit 1
}
$zipPath = Join-Path $distDir "$id-$version.zip"

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

& $Blender --factory-startup --command extension build --source-dir $sourceDir --output-dir $distDir
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed (Blender exit code $LASTEXITCODE)." -ForegroundColor Red
    exit $LASTEXITCODE
}
if (-not (Test-Path -LiteralPath $zipPath)) {
    Write-Host "Build finished but $zipPath was not created." -ForegroundColor Red
    exit 1
}

# Check the layout Blender's "Install from Disk" needs
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $entries = @($zip.Entries | ForEach-Object { $_.FullName })
}
finally {
    $zip.Dispose()
}
$problems = @()
foreach ($required in 'blender_manifest.toml', '__init__.py') {
    if ($entries -notcontains $required) {
        $problems += "$required is not at the top of the zip"
    }
}
if ($entries | Where-Object { $_ -like '*__pycache__*' }) {
    $problems += 'the zip contains __pycache__ folders'
}
if ($problems) {
    $problems | ForEach-Object { Write-Host "Zip check failed: $_" -ForegroundColor Red }
    exit 1
}

Write-Host ''
Write-Host "Built $zipPath ($($entries.Count) files)" -ForegroundColor Green
Write-Host 'Install: Blender > Edit > Preferences > Get Extensions > menu at the top right > Install from Disk.'
exit 0
