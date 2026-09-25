$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$cli = Join-Path $projectRoot 'dist\easy_gcode_plot_cli.exe'
$inputDirectory = Join-Path $projectRoot 'tests\fixtures\turning'
$outputDirectory = Join-Path ([System.IO.Path]::GetTempPath()) 'easy_gcode_plot\batch_export\turning'

if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) {
    throw "CLI executable not found: $cli"
}

& $cli batch-export $inputDirectory `
    --lang fanuc_turn --encoding utf-8 --format nc --mode expanded `
    --units auto --no-sequence-numbers --spaces --no-leading-zero --comments `
    -o $outputDirectory
exit $LASTEXITCODE
