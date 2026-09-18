[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$ToolProjectRoot = $ProjectRoot
)
$ErrorActionPreference = 'Stop'
$projectRootPath = (Resolve-Path -LiteralPath $ProjectRoot).Path
$toolProjectRootPath = (Resolve-Path -LiteralPath $ToolProjectRoot).Path
$powerShellExe = (Get-Process -Id $PID).Path
$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('easy-gcode-plot-qt-' + [guid]::NewGuid().ToString('N'))
$stagedUi = Join-Path $stagingRoot 'ui'
$stagedResources = Join-Path $stagingRoot 'resources'
try {
    New-Item -ItemType Directory -Path $stagedUi, $stagedResources -Force | Out-Null
    & $powerShellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'generate-translations.ps1') -ProjectRoot $projectRootPath -ToolProjectRoot $toolProjectRootPath
    if ($LASTEXITCODE -ne 0) { throw "Qt translation generation failed (exit $LASTEXITCODE)" }
    & $powerShellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'generate-resources.ps1') -ProjectRoot $projectRootPath -OutputDirectory $stagedResources -ToolProjectRoot $toolProjectRootPath
    if ($LASTEXITCODE -ne 0) { throw "Qt resource generation failed (exit $LASTEXITCODE)" }
    & $powerShellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'generate-ui.ps1') -ProjectRoot $projectRootPath -OutputDirectory $stagedUi -ToolProjectRoot $toolProjectRootPath
    if ($LASTEXITCODE -ne 0) { throw "Qt UI generation failed (exit $LASTEXITCODE)" }
    $generatedDirPath = (Resolve-Path -LiteralPath (Join-Path $projectRootPath 'app\ui\generated')).Path
    $expectedUi = @(
        Get-ChildItem -LiteralPath $generatedDirPath -Filter '*.ui' -File -Recurse | Sort-Object FullName | ForEach-Object {
            $relativeDir = $_.DirectoryName.Substring($generatedDirPath.Length).TrimStart('\')
            $name = if ($_.BaseName -eq 'main_window') { 'main_ui.py' } else { "$($_.BaseName).py" }
            if ($relativeDir) { Join-Path $relativeDir $name } else { $name }
        }
    )
    foreach ($relative in $expectedUi) {
        if (-not (Test-Path -LiteralPath (Join-Path $stagedUi $relative))) { throw "Missing staged UI output: $relative" }
    }
    Copy-Item -LiteralPath (Join-Path $stagedResources 'files_res.py') -Destination (Join-Path $projectRootPath 'app\resources\files_res.py') -Force
    foreach ($relative in $expectedUi) {
        $destination = Join-Path $generatedDirPath $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $stagedUi $relative) -Destination $destination -Force
    }
    Write-Host 'All Qt generated modules are up to date.' -ForegroundColor Green
}
finally { if (Test-Path -LiteralPath $stagingRoot) { Remove-Item -LiteralPath $stagingRoot -Recurse -Force } }
