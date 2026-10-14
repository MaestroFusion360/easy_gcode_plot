[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Path = 'tests',

    [switch]$NoSync,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraPytestArgs
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

Push-Location $projectRoot
try {
    $uvArguments = @('run')

    if ($NoSync) {
        $uvArguments += '--no-sync'
    }

    if (-not [string]::IsNullOrWhiteSpace($env:VIRTUAL_ENV)) {
        $uvArguments += '--active'
    }

    $uvArguments += @('pytest', '-q', $Path)
    $uvArguments += $ExtraPytestArgs

    if ($VerbosePreference -ne 'SilentlyContinue') {
        $uvArguments += '-v'
    }

    & uv @uvArguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}