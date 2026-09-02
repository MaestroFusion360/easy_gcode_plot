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
    & uv sync --locked --group dev --group build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if (-not $SkipTests) {
        & uv run pytest tests
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    $arguments = @(
        'run', 'pyinstaller',
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
