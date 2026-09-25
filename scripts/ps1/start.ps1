[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

Push-Location $projectRoot
try {
    & uv run python main.py @Arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
