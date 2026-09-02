[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

Push-Location $projectRoot
try {
    & uv sync --locked --group dev
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
