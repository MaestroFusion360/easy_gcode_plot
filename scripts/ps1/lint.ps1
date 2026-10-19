[CmdletBinding()]
param(
    [switch]$Fix,
    [switch]$CheckResources,
    [switch]$NoSync
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$targets = @('main.py', 'cli_main.py', 'app', 'tests', 'scripts/check_complexity.py', 'scripts/check_line_endings.py', 'scripts/analyze_project.py')
$uvRunArguments = @('run')
$previousUvNoSync = $env:UV_NO_SYNC
if ($NoSync) { $uvRunArguments += '--no-sync' }
if (-not [string]::IsNullOrWhiteSpace($env:VIRTUAL_ENV)) {
    $uvRunArguments += '--active'
}

Push-Location $projectRoot

try {
    if ($NoSync) { $env:UV_NO_SYNC = '1' }
    $lineEndingArguments = @('python', 'scripts/check_line_endings.py')
    if ($Fix) { $lineEndingArguments += '--fix' }
    & uv @uvRunArguments @lineEndingArguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    if ($Fix) {
        & uv @uvRunArguments ruff format @targets
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        & uv @uvRunArguments ruff check @targets --fix
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        & (Join-Path $PSScriptRoot 'generate-resources.ps1') -ProjectRoot $projectRoot
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        # Qt generators may produce LF; normalize their output after generation.
        & uv @uvRunArguments @lineEndingArguments
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
    else {
        & uv @uvRunArguments ruff format --check @targets
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        & uv @uvRunArguments ruff check @targets
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }

    & uv @uvRunArguments python scripts/check_ui_format.py
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $qtCheckArguments = @('python', 'scripts/check_qt_sources.py')
    if ($CheckResources) {
        $qtCheckArguments += '--check-resources'
    }
    & uv @uvRunArguments @qtCheckArguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & uv @uvRunArguments python scripts/check_complexity.py
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & uv @uvRunArguments lint-imports --contract kernel-boundaries --no-logo --no-cache
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & uv @uvRunArguments pylint @targets
    exit $LASTEXITCODE
}
finally {
    if ($NoSync) { [Environment]::SetEnvironmentVariable('UV_NO_SYNC', $previousUvNoSync, 'Process') }
    Pop-Location
}
