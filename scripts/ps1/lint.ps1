[CmdletBinding()]
param(
    [switch]$Fix,
    [switch]$CheckResources
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$targets = @('main.py', 'app', 'tests', 'scripts/check_complexity.py')
$uvRunArguments = @('run')
if (-not [string]::IsNullOrWhiteSpace($env:VIRTUAL_ENV)) {
    $uvRunArguments += '--active'
}

Push-Location $projectRoot

try {
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

    & uv @uvRunArguments pylint @targets
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
