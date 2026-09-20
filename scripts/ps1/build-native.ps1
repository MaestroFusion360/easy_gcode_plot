[CmdletBinding()]
param(
    [string]$BuildEnvironment,
    [switch]$Refresh
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ([string]::IsNullOrWhiteSpace($BuildEnvironment)) {
    $BuildEnvironment = Join-Path $projectRoot '.venv-build'
}

$python = Join-Path $BuildEnvironment 'Scripts\python.exe'
$dependencyStateFile = Join-Path $BuildEnvironment '.easy-gcode-plot-dependencies-state'
$nativeStateFile = Join-Path $BuildEnvironment '.easy-gcode-plot-native-state'

$dependencyInputs = @(
    (Join-Path $projectRoot 'pyproject.toml'),
    (Join-Path $projectRoot 'uv.lock')
)

$nativeInputs = @(
    (Join-Path $projectRoot 'app\gcode\kernel\frontend\_native_parser.pyx'),
    (Join-Path $projectRoot 'app\gcode\kernel\milling\_native_executor.pyx'),
    (Join-Path $projectRoot 'app\tools\_native_discovery.pyx')
)

function Get-BuildState {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Paths
    )

    $parts = foreach ($path in $Paths) {
        if (-not (Test-Path $path)) {
            throw "Build input is missing: $path"
        }

        $hash = (Get-FileHash -Algorithm SHA256 $path).Hash
        "{0}:{1}" -f (Split-Path $path -Leaf), $hash
    }

    return ($parts -join "`n")
}

function Read-State {
    param([string]$Path)

    if (Test-Path $Path) {
        return Get-Content -Raw $Path
    }

    return ''
}

function Write-State {
    param(
        [string]$Path,
        [string]$Value
    )

    Set-Content -Path $Path -Value $Value -NoNewline -Encoding ascii
}

function Test-PythonModule {
    param(
        [string]$Python,
        [string]$Module
    )

    if (-not (Test-Path $Python)) {
        return $false
    }

    & $Python -c "import $Module" *> $null
    return ($LASTEXITCODE -eq 0)
}

function Invoke-BuildSync {
    param(
        [switch]$ReinstallProject,
        [switch]$ReinstallPyInstaller
    )

    $hadProjectEnvironment = Test-Path Env:UV_PROJECT_ENVIRONMENT
    $previousProjectEnvironment = $env:UV_PROJECT_ENVIRONMENT
    $hadVirtualEnvironment = Test-Path Env:VIRTUAL_ENV
    $previousVirtualEnvironment = $env:VIRTUAL_ENV

    try {
        # Build/release dependencies live only in .venv-build.
        $env:UV_PROJECT_ENVIRONMENT = $BuildEnvironment
        Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue

        $arguments = @(
            'sync',
            '--locked',
            '--no-dev',
            '--group', 'build'
        )

        if ($ReinstallProject) {
            $arguments += @('--reinstall-package', 'easy-gcode-plot')
        }

        if ($ReinstallPyInstaller) {
            $arguments += @('--reinstall-package', 'pyinstaller')
        }

        & uv @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "uv sync failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        if ($hadProjectEnvironment) {
            $env:UV_PROJECT_ENVIRONMENT = $previousProjectEnvironment
        }
        else {
            Remove-Item Env:UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
        }

        if ($hadVirtualEnvironment) {
            $env:VIRTUAL_ENV = $previousVirtualEnvironment
        }
        else {
            Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
        }
    }
}

Push-Location $projectRoot
try {
    $dependencyState = Get-BuildState -Paths $dependencyInputs
    $nativeState = Get-BuildState -Paths $nativeInputs

    $savedDependencyState = Read-State -Path $dependencyStateFile
    $savedNativeState = Read-State -Path $nativeStateFile

    $needsDependencySync = $Refresh.IsPresent
    if (-not (Test-Path $python)) { $needsDependencySync = $true }
    if ($savedDependencyState -ne $dependencyState) { $needsDependencySync = $true }

    if ($needsDependencySync) {
        Write-Host 'Refreshing build dependencies...'
        Invoke-BuildSync -ReinstallProject
    }
    elseif ($savedNativeState -ne $nativeState) {
        Write-Host 'Build dependencies are up to date; dependency sync skipped.'
        Write-Host 'Native sources changed; rebuilding easy-gcode-plot only...'
        Invoke-BuildSync -ReinstallProject
    }
    else {
        Write-Host 'Build dependencies are up to date; dependency sync skipped.'
        Write-Host 'Native extensions are up to date; rebuild skipped.'
    }

    # Repair PyInstaller only if the module is actually missing. This is not run
    # on normal builds.
    if (-not (Test-PythonModule -Python $python -Module 'PyInstaller')) {
        Write-Host 'PyInstaller module is missing; repairing build environment once...'
        Invoke-BuildSync -ReinstallPyInstaller
    }

    if (-not (Test-PythonModule -Python $python -Module 'PyInstaller')) {
        throw "PyInstaller module is unavailable in build environment: $BuildEnvironment"
    }

    # Feed verification code through stdin to avoid PowerShell quote mangling.
    $nativeCheck = @'
import app.gcode.kernel.frontend._native_parser as parser
import app.gcode.kernel.milling._native_executor as executor
import app.tools._native_discovery as discovery

print("Native parser:   " + parser.__file__)
print("Native executor: " + executor.__file__)
print("Native discovery: " + discovery.__file__)
print("Native acceleration is ready.")
'@

    $nativeCheck | & $python -
    if ($LASTEXITCODE -ne 0) {
        throw "Native acceleration verification failed with exit code $LASTEXITCODE"
    }

    # Persist state only after both native and build-tool verification succeeded.
    Write-State -Path $dependencyStateFile -Value $dependencyState
    Write-State -Path $nativeStateFile -Value $nativeState
}
finally {
    Pop-Location
}
