# build.ps1 - Package RigWeaver addon for Blender 4.5+ Extensions distribution
#
# Usage:
#   .\build.ps1
# Or if execution policy is restrictive:
#   powershell -ExecutionPolicy Bypass -File build.ps1

$ProjectRoot = $PSScriptRoot
$ManifestPath = Join-Path $ProjectRoot "blender_manifest.toml"

# Read version from manifest
$ManifestContent = Get-Content $ManifestPath -Raw
if ($ManifestContent -match 'version\s*=\s*"([^"]+)"') {
    $Version = $Matches[1]
} else {
    Write-Error "Could not parse version from blender_manifest.toml"
    exit 1
}

# Use manifest display name for artifact naming, normalized for filesystem safety.
if ($ManifestContent -match 'name\s*=\s*"([^"]+)"') {
    $AddonName = $Matches[1]
} else {
    $AddonName = "addon"
}

$NormalizedAddonName = $AddonName -replace '[^A-Za-z0-9]+', '_'
$NormalizedAddonName = $NormalizedAddonName -replace '_+', '_'
$NormalizedAddonName = $NormalizedAddonName.Trim('_')
if ([string]::IsNullOrWhiteSpace($NormalizedAddonName)) {
    $NormalizedAddonName = "addon"
}

$OutputName = "${NormalizedAddonName}_v$Version.zip"
$OutputPath = Join-Path $ProjectRoot $OutputName

# Remove existing zip with the same name
if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
    Write-Host "Removed existing $OutputName"
}

# Stage files in a temp directory so Compress-Archive produces a flat zip root
# (Blender 4.x Extensions require no wrapping folder inside the zip)
$TempDir = Join-Path $env:TEMP "blender_bone_util_build"
if (Test-Path $TempDir) { Remove-Item $TempDir -Recurse -Force }
New-Item -ItemType Directory -Path $TempDir | Out-Null

# Root files
Copy-Item (Join-Path $ProjectRoot "__init__.py")           $TempDir
Copy-Item (Join-Path $ProjectRoot "blender_manifest.toml") $TempDir
Copy-Item (Join-Path $ProjectRoot "translations.py")       $TempDir

# Subdirectories - copy only .py files (excludes __pycache__, *.pyc, etc.)
foreach ($Dir in @("operators", "ui")) {
    $DestDir = Join-Path $TempDir $Dir
    New-Item -ItemType Directory -Path $DestDir | Out-Null
    Get-ChildItem (Join-Path $ProjectRoot $Dir) -Filter "*.py" |
        Copy-Item -Destination $DestDir
}

# Count staged files
$StagedFiles = (Get-ChildItem $TempDir -Recurse -File).Count

# Zip the contents (wildcard avoids creating a wrapper folder in the zip)
Compress-Archive -Path "$TempDir\*" -DestinationPath $OutputPath

# Clean up temp directory
Remove-Item $TempDir -Recurse -Force

Write-Host "Built: $OutputPath ($StagedFiles files)"
