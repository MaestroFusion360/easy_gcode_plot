$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path

Push-Location $projectRoot
try {
    & .\dist\easy_gcode_plot_cli.exe batch-export tests\fixtures\milling\sinumerik `
        --lang fanuc_mill `
        --mode expanded `
        --post-profile app\gcode\export\posts\fanuc_mill.json `
        -o tmp\test_export\sinumerik_native_to_fanuc_mill
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $exitCode
