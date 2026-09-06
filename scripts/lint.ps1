[CmdletBinding()]
param(
    [switch]$Fix
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$targets = @('main.py', 'app', 'tests')
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

    & uv @uvRunArguments pylint @targets
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
