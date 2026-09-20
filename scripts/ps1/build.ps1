[CmdletBinding()]
param(
    [switch]$Console,
    [switch]$SkipTests,
    [switch]$RefreshBuildEnvironment
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$entryPoint = Join-Path $projectRoot 'main.py'
$separator = [System.IO.Path]::PathSeparator
$buildEnvironment = Join-Path $projectRoot '.venv-build'
$python = Join-Path $buildEnvironment 'Scripts\python.exe'

Push-Location $projectRoot
try {
    if (-not $SkipTests) {
        & (Join-Path $PSScriptRoot 'test.ps1')
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    & (Join-Path $PSScriptRoot 'build-native.ps1') `
        -BuildEnvironment $buildEnvironment `
        -Refresh:$RefreshBuildEnvironment
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if (-not (Test-Path $python)) {
        throw "Build Python is missing: $python"
    }

    # Do not depend on a pyinstaller.exe launcher. The locked build environment
    # only needs the PyInstaller module to be installed.
    & $python -c 'import PyInstaller' *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller module is missing from build environment: $buildEnvironment"
    }

    $arguments = @(
        '-m', 'PyInstaller',
        '--noconfirm',
        '--clean',
        '--onefile',
        '--name', 'easy_gcode_plot',
        '--icon', (Join-Path $projectRoot 'logo.ico'),
        '--specpath', (Join-Path $projectRoot 'build\pyinstaller'),
        '--workpath', (Join-Path $projectRoot 'build\pyinstaller\work'),
        '--distpath', (Join-Path $projectRoot 'dist'),
        '--collect-submodules', 'app.gcode.export',
        '--add-data', "$(Join-Path $projectRoot 'pyproject.toml')${separator}."
    )

    $arguments += if ($Console) { '--console' } else { '--windowed' }
    $arguments += $entryPoint

    & $python @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
