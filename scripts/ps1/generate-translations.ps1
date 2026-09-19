[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$ToolProjectRoot = $ProjectRoot
)
$ErrorActionPreference = 'Stop'
$projectRootPath = (Resolve-Path -LiteralPath $ProjectRoot).Path
$toolProjectRootPath = (Resolve-Path -LiteralPath $ToolProjectRoot).Path
$translationsDir = Join-Path $projectRootPath 'translations'
$outputDir = Join-Path $projectRootPath 'app\resources\translations'
New-Item -ItemType Directory -Path $translationsDir, $outputDir -Force | Out-Null

$tsFiles = @(Get-ChildItem -LiteralPath $translationsDir -Filter '*.ts' -File | Sort-Object Name)
if ($tsFiles.Count -eq 0) {
    Write-Host "No .ts translation sources found in $translationsDir; skipping translation generation." -ForegroundColor Yellow
    return
}

$sources = @()
$generatedUiDir = Join-Path $projectRootPath 'app\ui\generated'
if (Test-Path -LiteralPath $generatedUiDir) {
    $sources += @(Get-ChildItem -LiteralPath $generatedUiDir -Filter '*.ui' -File -Recurse | ForEach-Object { $_.FullName })
}
foreach ($relativeDir in @('app\ui\dialogs', 'app\ui\windows', 'app\ui\plot', 'app\ui\support')) {
    $sourceDir = Join-Path $projectRootPath $relativeDir
    if (Test-Path -LiteralPath $sourceDir) {
        $sources += @(Get-ChildItem -LiteralPath $sourceDir -Filter '*.py' -File -Recurse | ForEach-Object { $_.FullName })
    }
}
foreach ($relativeFile in @('app\main_window.py', 'app\application.py', 'app\tools\definitions.py')) {
    $sourceFile = Join-Path $projectRootPath $relativeFile
    if (Test-Path -LiteralPath $sourceFile) { $sources += $sourceFile }
}
if ($sources.Count -eq 0) {
    Write-Host "No translation sources found in $projectRootPath; skipping translation generation." -ForegroundColor Yellow
    return
}

$lupdateArguments = @('run', '--directory', $toolProjectRootPath, '--locked', '--group', 'dev', 'pyside6-lupdate')
$lupdateArguments += $sources
$lupdateArguments += @('-extensions', 'py', '-no-obsolete', '-ts')
$lupdateArguments += ($tsFiles | ForEach-Object { $_.FullName })
& uv @lupdateArguments
if ($LASTEXITCODE -ne 0) { throw "pyside6-lupdate failed (exit $LASTEXITCODE)" }

foreach ($tsFile in $tsFiles) {
    $qm = Join-Path $outputDir ($tsFile.BaseName + '.qm')
    & uv run --directory $toolProjectRootPath --locked --group dev pyside6-lrelease $tsFile.FullName -qm $qm
    if ($LASTEXITCODE -ne 0) { throw "pyside6-lrelease failed for $($tsFile.FullName) (exit $LASTEXITCODE)" }
    Write-Host "Generated $qm" -ForegroundColor Green
}

# The compiled catalogs are embedded in the Qt resource module.  Refresh it so
# the generated resource and the runtime translator never drift apart.
& (Join-Path $PSScriptRoot 'generate-resources.ps1') -ProjectRoot $projectRootPath -ToolProjectRoot $toolProjectRootPath
if (-not $?) { throw 'Qt resource generation failed after translations' }
