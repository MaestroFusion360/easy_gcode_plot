[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$OutputDirectory = '',
    [string]$ToolProjectRoot = $ProjectRoot
)
$ErrorActionPreference = 'Stop'
$projectRootPath = (Resolve-Path -LiteralPath $ProjectRoot).Path
$toolProjectRootPath = (Resolve-Path -LiteralPath $ToolProjectRoot).Path
$source = Join-Path $projectRootPath 'app\resources\files_res.qrc'
$resourceDir = Split-Path -Parent $source
if (-not $OutputDirectory) { $OutputDirectory = $resourceDir }
$outputDirPath = [System.IO.Path]::GetFullPath($OutputDirectory)
$target = Join-Path $outputDirPath 'files_res.py'
$tempFile = Join-Path $outputDirPath ('.rcc-' + [guid]::NewGuid().ToString('N') + '.tmp')
$utf8 = New-Object System.Text.UTF8Encoding($false)

New-Item -ItemType Directory -Path $outputDirPath -Force | Out-Null
try {
    [xml]$manifest = Get-Content -Raw -LiteralPath $source
    $seen = @{}
    foreach ($entry in $manifest.RCC.qresource.file) {
        $relative = [string]$entry.'#text'
        if (-not $relative) { $relative = [string]$entry }
        if (-not (Test-Path -LiteralPath (Join-Path $resourceDir $relative) -PathType Leaf)) { throw "Qt resource manifest references a missing file: $relative ($source)" }
        if ($seen.ContainsKey($relative)) { throw "Duplicate Qt resource entry '$relative' in $source" }
        $seen[$relative] = $true
    }
    & uv run --directory $toolProjectRootPath --locked --group dev pyside6-rcc $source -o $tempFile
    if ($LASTEXITCODE -ne 0) { throw "pyside6-rcc failed for $source (exit $LASTEXITCODE)" }
    $content = [regex]::Replace([System.IO.File]::ReadAllText($tempFile), '(?m)^from PySide6(?=[ .])', 'from PyQt6')
    $newline = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
    $content = $content.TrimEnd([char[]]"`r`n") + $newline
    if ($content -match '(?m)^\s*(?:from|import)\s+PySide6') { throw "Generated resource module still imports PySide6: $source" }
    [System.IO.File]::WriteAllText($target, $content, $utf8)
    Write-Host "Generated $target" -ForegroundColor Green
}
finally { if (Test-Path -LiteralPath $tempFile) { Remove-Item -LiteralPath $tempFile -Force } }
