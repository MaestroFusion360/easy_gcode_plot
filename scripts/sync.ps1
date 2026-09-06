[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

Push-Location $projectRoot
try {
    $syncArguments = @('sync', '--locked', '--group', 'dev')
    if (-not [string]::IsNullOrWhiteSpace($env:VIRTUAL_ENV)) {
        $syncArguments += '--active'
    }
    & uv @syncArguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
