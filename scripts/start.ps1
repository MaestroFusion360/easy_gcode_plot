[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

Push-Location $projectRoot
try {
    & uv run python main.py
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
