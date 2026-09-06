[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Path = 'tests'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

Push-Location $projectRoot
try {
    $pytestArguments = @('run')
    if (-not [string]::IsNullOrWhiteSpace($env:VIRTUAL_ENV)) {
        $pytestArguments += '--active'
    }
    $pytestArguments += @('pytest', $Path)
    if ($VerbosePreference -ne 'SilentlyContinue') {
        $pytestArguments += '-v'
    }

    & uv @pytestArguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
