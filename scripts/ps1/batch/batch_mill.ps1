$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$cli = Join-Path $projectRoot 'dist\easy_gcode_plot_cli.exe'
$inputDirectory = Join-Path $projectRoot 'tests\fixtures\milling'
$outputDirectory = Join-Path ([System.IO.Path]::GetTempPath()) 'easy_gcode_plot\batch\milling'

if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) {
    throw "CLI executable not found: $cli"
}

& $cli batch $inputDirectory --lang fanuc_mill --encoding utf-8 -o $outputDirectory
exit $LASTEXITCODE
