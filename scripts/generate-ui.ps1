[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$OutputDirectory = '',
    [string]$ToolProjectRoot = $ProjectRoot
)
$ErrorActionPreference = 'Stop'
$projectRootPath = (Resolve-Path -LiteralPath $ProjectRoot).Path
$toolProjectRootPath = (Resolve-Path -LiteralPath $ToolProjectRoot).Path
$generatedDir = Join-Path $projectRootPath 'app\ui\generated'
if (-not $OutputDirectory) { $OutputDirectory = $generatedDir }
$outputDirPath = [System.IO.Path]::GetFullPath($OutputDirectory)
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Get-GeneratedFileName([System.IO.FileInfo]$UiFile) {
    if ($UiFile.BaseName -eq 'main_window') { return 'main_ui.py' }
    return "$($UiFile.BaseName).py"
}
function Convert-GeneratedUiCode([string]$Content) {
    $result = [regex]::Replace($Content, '(?m)^from PySide6(?=[ .])', 'from PyQt6')
    # Older Designer sources can make pyside6-uic emit Qt5-style enum aliases
    # which PyQt6 intentionally does not expose.
    $enumAliases = @{
        'Qt.Horizontal' = 'Qt.Orientation.Horizontal'
        'Qt.Vertical' = 'Qt.Orientation.Vertical'
        'QDialogButtonBox.Ok' = 'QDialogButtonBox.StandardButton.Ok'
        'QDialogButtonBox.Cancel' = 'QDialogButtonBox.StandardButton.Cancel'
    }
    foreach ($alias in $enumAliases.Keys) { $result = $result.Replace($alias, $enumAliases[$alias]) }
    $result = [regex]::Replace($result, '(?m)^(?:from\s+\S+\s+import\s+files_res_rc|import\s+files_res_rc)\r?\n', '')
    if ($result.Contains(':/resource/') -and -not $result.Contains('import app.resources.files_res')) {
        $newline = if ($result.Contains("`r`n")) { "`r`n" } else { "`n" }
        $classPattern = [regex]::new('(?m)^class Ui_')
        $replacement = 'import app.resources.files_res  # noqa: F401  # Registers Qt resources on import.' + $newline + $newline + 'class Ui_'
        $result = $classPattern.Replace($result, $replacement, 1)
    }
    $finalNewline = if ($result.Contains("`r`n")) { "`r`n" } else { "`n" }
    return $result.TrimEnd([char[]]"`r`n") + $finalNewline
}

New-Item -ItemType Directory -Path $outputDirPath -Force | Out-Null
$uiFiles = @(Get-ChildItem -LiteralPath $generatedDir -Filter '*.ui' -File | Sort-Object Name)
if ($uiFiles.Count -eq 0) { throw "No Qt Designer .ui files found in $generatedDir" }
foreach ($uiFile in $uiFiles) {
    $target = Join-Path $outputDirPath (Get-GeneratedFileName $uiFile)
    $tempFile = Join-Path $outputDirPath ('.uic-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        & uv run --directory $toolProjectRootPath --locked --group dev pyside6-uic $uiFile.FullName -o $tempFile
        if ($LASTEXITCODE -ne 0) { throw "pyside6-uic failed for $($uiFile.FullName) (exit $LASTEXITCODE)" }
        $content = Convert-GeneratedUiCode ([System.IO.File]::ReadAllText($tempFile))
        if ($content -match '(?m)^\s*(?:from|import)\s+PySide6') { throw "Generated UI module still imports PySide6: $($uiFile.FullName)" }
        [System.IO.File]::WriteAllText($target, $content, $utf8)
        Write-Host "Generated $target" -ForegroundColor Green
    }
    finally { if (Test-Path -LiteralPath $tempFile) { Remove-Item -LiteralPath $tempFile -Force } }
}
