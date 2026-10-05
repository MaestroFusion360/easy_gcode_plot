[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = 'Stop'
$nativeModules = @(
    @{ Directory = 'app\gcode\kernel\frontend'; Name = '_native_parser' },
    @{ Directory = 'app\gcode\kernel\milling'; Name = '_native_executor' },
    @{ Directory = 'app\tools'; Name = '_native_discovery' }
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
            $owners = foreach ($process in Get-Process) {
                try {
                    foreach ($module in $process.Modules) {
                        if ($module.FileName -eq $file.FullName) {
                            "$($process.ProcessName) (PID $($process.Id))"
                            break
                        }
                    }
                }
                catch {
                    # Windows may deny access to unrelated processes.
                }
            }
            $ownerText = if ($owners) { " Loaded by: $($owners -join ', ')." } else { '' }
            throw "Native extension cannot be replaced: $($file.FullName).$ownerText Close the running application or Python session using this project, then retry the build. No processes were terminated. Windows error: $($_.Exception.Message)"
        }
    }
}
