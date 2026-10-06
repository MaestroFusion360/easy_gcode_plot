$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path

Push-Location $projectRoot
try {
    & .\dist\easy_gcode_plot_cli.exe batch-export tests\fixtures\milling\fanuc `
        --lang fanuc_mill `
        --mode expanded `
        --post-profile app\gcode\export\posts\sinumerik_840d.json `
        -o tmp\test_export\fanuc_mill_to_sinumerik_native
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $exitCode
