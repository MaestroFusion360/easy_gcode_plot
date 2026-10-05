[CmdletBinding()]
param(
    [switch]$Automated,
    [ValidateRange(0, 60000)]
    [int]$DelayMs = 1000
)

$ErrorActionPreference = 'Stop'
$names = @('QT_QPA_PLATFORM', 'EASY_GCODE_SMOKE_DEMO', 'EASY_GCODE_SMOKE_DELAY_MS')
$previous = @{}
foreach ($name in $names) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
    if ($Automated) {
        $env:QT_QPA_PLATFORM = 'offscreen'
        $env:EASY_GCODE_SMOKE_DEMO = '0'
    }
    else {
        $env:QT_QPA_PLATFORM = 'windows'
        $env:EASY_GCODE_SMOKE_DEMO = '1'
    }
    $env:EASY_GCODE_SMOKE_DELAY_MS = [string]$DelayMs
    & (Join-Path $PSScriptRoot 'test.ps1') -Path 'tests/gui/test_daily_workflow_smoke.py' -ExtraPytestArgs @('-q', '-s')
    $exitCode = $LASTEXITCODE
}
finally {
    foreach ($name in $names) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
}
exit $exitCode
