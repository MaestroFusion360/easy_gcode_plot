$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$cli = Join-Path $projectRoot 'dist\easy_gcode_plot_cli.exe'
$inputDirectory = Join-Path $projectRoot 'tests\fixtures\milling'
$outputDirectory = Join-Path ([System.IO.Path]::GetTempPath()) 'easy_gcode_plot\batch_export\milling'

if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) {
    throw "CLI executable not found: $cli"
}

& $cli batch-export $inputDirectory `
    --lang fanuc_mill --encoding utf-8 --format nc --mode expanded `
    --units auto --arc-type auto --no-sequence-numbers --spaces `
    --no-leading-zero --comments -o $outputDirectory
exit $LASTEXITCODE
