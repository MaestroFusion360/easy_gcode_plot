[CmdletBinding()]
param(
    [switch]$Console,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$entryPoint = Join-Path $projectRoot 'main.py'
$separator = [System.IO.Path]::PathSeparator

Push-Location $projectRoot
try {
    if (-not $SkipTests) {
        & (Join-Path $PSScriptRoot 'test.ps1')
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    $arguments = @(
        'run', '--isolated', '--locked', '--no-dev', '--group', 'build', 'pyinstaller',
        '--noconfirm',
        '--clean',
        '--onefile',
        '--name', 'easy_gcode_plot',
        '--icon', (Join-Path $projectRoot 'logo.ico'),
        '--specpath', (Join-Path $projectRoot 'build\pyinstaller'),
        '--workpath', (Join-Path $projectRoot 'build\pyinstaller\work'),
        '--distpath', (Join-Path $projectRoot 'dist'),
        '--add-data', "$(Join-Path $projectRoot 'pyproject.toml')${separator}."
    )
    $arguments += if ($Console) { '--console' } else { '--windowed' }
    $arguments += $entryPoint

    & uv @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
