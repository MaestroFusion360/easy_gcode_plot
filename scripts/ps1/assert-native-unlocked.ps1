[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = 'Stop'
$nativeModules = @(
    @{ Directory = 'app\gcode\kernel\frontend'; Name = '_native_parser' },
    @{ Directory = 'app\gcode\kernel\milling'; Name = '_native_executor' },
    @{ Directory = 'app\tools'; Name = '_native_discovery' },
    @{ Directory = 'app\gcode\stock'; Name = '_native_turning_collision' }
)

foreach ($nativeModule in $nativeModules) {
    $directory = Join-Path $ProjectRoot $nativeModule.Directory
    if (-not (Test-Path -LiteralPath $directory)) { continue }

    $files = Get-ChildItem -LiteralPath $directory -Filter "$($nativeModule.Name)*.pyd" -File
    foreach ($file in $files) {
        try {
            $stream = [System.IO.File]::Open(
                $file.FullName,
                [System.IO.FileMode]::Open,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
            $stream.Dispose()
        }
        catch {
            [Console]::Error.WriteLine(
                "Close the running application or Python session using this project, then retry the build."
            )
            throw "Native extension cannot be replaced: $($file.FullName). Close the running application or Python session using this project, then retry the build. No processes were terminated. Windows error: $($_.Exception.Message)"
        }
    }
}
