[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Path = 'tests',

    [switch]$NoSync,

    [ValidateRange(0, 64)]
    [int]$Workers = 4,

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

    if ($Workers -gt 0) {
        # Whole files stay on one worker: module-scoped Qt fixtures and the qt-codegen
        # subprocess tests must not interleave with other workers.
        $uvArguments += @('-n', "$Workers", '--dist', 'loadfile')
    }

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
