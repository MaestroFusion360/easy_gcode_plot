[CmdletBinding()]
param(
    [switch]$Fix
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$targets = @('main.py', 'app', 'tests')

Push-Location $projectRoot

try {
    if ($Fix) {
        & uv run ruff format @targets
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        & uv run ruff check @targets --fix
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
    else {
        & uv run ruff format --check @targets
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }

        & uv run ruff check @targets
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }

    & uv run pylint @targets
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
