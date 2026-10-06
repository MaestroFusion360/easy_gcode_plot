$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path

Push-Location $projectRoot
try {
    & .\dist\easy_gcode_plot_cli.exe batch-export tests\fixtures\turning `
        --lang fanuc_turn `
        --lathe-gcode-system A `
        --mode expanded `
        --post-profile app\gcode\export\posts\fanuc_lathe_b.json `
        -o tmp\test_export\fanuc_lathe_a_to_b
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $exitCode
