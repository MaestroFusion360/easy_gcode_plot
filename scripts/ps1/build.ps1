[CmdletBinding()]
param(
    [switch]$Console,
    [switch]$SkipTests,
    [switch]$RefreshBuildEnvironment
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$separator = [System.IO.Path]::PathSeparator
$buildEnvironment = Join-Path $projectRoot '.venv-build'
$python = Join-Path $buildEnvironment 'Scripts\python.exe'
$distPath = Join-Path $projectRoot 'dist'

function Write-ExeChecksum {
    param([Parameter(Mandatory)][string]$ExeName)

    $exePath = Join-Path $distPath $ExeName
    $hash = (Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $checksumPath = "$exePath.sha256"
    "$hash *$ExeName" | Set-Content -LiteralPath $checksumPath -Encoding ascii
    Write-Host "SHA-256: $hash  $ExeName"
}

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
        '--icon', (Join-Path $projectRoot 'logo.ico'),
        '--specpath', (Join-Path $projectRoot 'build\pyinstaller'),
        '--workpath', (Join-Path $projectRoot 'build\pyinstaller\work'),
        '--distpath', $distPath,
        '--collect-submodules', 'app.gcode.export',
        '--add-data', "$(Join-Path $projectRoot 'pyproject.toml')${separator}."
    )

    if ($Console) {
        & $python @arguments --name easy_gcode_plot_cli --console (Join-Path $projectRoot 'cli_main.py')
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-ExeChecksum -ExeName 'easy_gcode_plot_cli.exe'
        exit 0
    }

    & $python @arguments --name easy_gcode_plot --windowed (Join-Path $projectRoot 'main.py')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-ExeChecksum -ExeName 'easy_gcode_plot.exe'
    & $python @arguments --name easy_gcode_plot_cli --console (Join-Path $projectRoot 'cli_main.py')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-ExeChecksum -ExeName 'easy_gcode_plot_cli.exe'
    exit 0
}
finally {
    Pop-Location
}
