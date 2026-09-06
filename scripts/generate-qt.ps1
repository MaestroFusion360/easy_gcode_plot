[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
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
    & $powerShellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'generate-resources.ps1') -ProjectRoot $projectRootPath -OutputDirectory $stagedResources -ToolProjectRoot $toolProjectRootPath
    if ($LASTEXITCODE -ne 0) { throw "Qt resource generation failed (exit $LASTEXITCODE)" }
    & $powerShellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'generate-ui.ps1') -ProjectRoot $projectRootPath -OutputDirectory $stagedUi -ToolProjectRoot $toolProjectRootPath
    if ($LASTEXITCODE -ne 0) { throw "Qt UI generation failed (exit $LASTEXITCODE)" }
    $expectedUi = @(Get-ChildItem -LiteralPath (Join-Path $projectRootPath 'app\ui\generated') -Filter '*.ui' -File | ForEach-Object { if ($_.BaseName -eq 'main_window') { 'main_ui.py' } else { "$($_.BaseName).py" } })
    foreach ($name in $expectedUi) {
        if (-not (Test-Path -LiteralPath (Join-Path $stagedUi $name))) { throw "Missing staged UI output: $name" }
    }
    Copy-Item -LiteralPath (Join-Path $stagedResources 'files_res.py') -Destination (Join-Path $projectRootPath 'app\resources\files_res.py') -Force
    foreach ($name in $expectedUi) { Copy-Item -LiteralPath (Join-Path $stagedUi $name) -Destination (Join-Path $projectRootPath "app\ui\generated\$name") -Force }
    Write-Host 'All Qt generated modules are up to date.' -ForegroundColor Green
}
finally { if (Test-Path -LiteralPath $stagingRoot) { Remove-Item -LiteralPath $stagingRoot -Recurse -Force } }
