param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [string]$Message,

    [switch]$Push
)

$ErrorActionPreference = "Stop"

function Run-Step {
    param(
        [string]$Title,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Title" -ForegroundColor Cyan

    $global:LASTEXITCODE = 0
    & $Command
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -ne 0) {
        throw "Step failed: $Title (exit code $ExitCode)"
    }
}

function Run-Lint {
    Write-Host ""
    Write-Host "==> Lint / format" -ForegroundColor Cyan

    $PowerShellExe = (Get-Process -Id $PID).Path

    & $PowerShellExe `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File (Join-Path $PSScriptRoot 'lint.ps1') `
        -Fix `
        -CheckResources

    $LintExitCode = $LASTEXITCODE

    if ($LintExitCode -ne 0) {
        throw "Lint failed (exit code $LintExitCode). Release aborted."
    }

    Write-Host "Lint completed successfully." -ForegroundColor Green

    $global:LASTEXITCODE = 0
}

$Tag = "v$Version"
$TagMessage = "Release $Version"

if (-not (Test-Path ".git")) {
    throw "Run this script from the repository root."
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    throw "Version must not be empty."
}

Write-Host ""
Write-Host "==> Verify project version" -ForegroundColor Cyan

$ProjectVersion = (& uv version --short | Out-String).Trim()

if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($ProjectVersion)) {
    throw "Unable to read the project version with 'uv version --short'."
}

if ($ProjectVersion -ne $Version) {
    throw "Requested release $Version does not match pyproject version $ProjectVersion."
}

Run-Lint

Run-Step "Tests" {
    & (Join-Path $PSScriptRoot 'test.ps1')
}

Run-Step "git diff --check" {
    $PreviousErrorActionPreference = $ErrorActionPreference

    try {
        $ErrorActionPreference = "Continue"

        git --no-pager diff --check 2>$null
        $GitDiffExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }

    $global:LASTEXITCODE = $GitDiffExitCode
}

Write-Host ""
Write-Host "==> Git status" -ForegroundColor Cyan
git status --short

Write-Host ""
Write-Host "==> Check release tag" -ForegroundColor Cyan

$LocalTag = git tag --list $Tag

$RemoteTagOutput = git ls-remote --tags origin "refs/tags/$Tag"
$RemoteTagExists = -not [string]::IsNullOrWhiteSpace(
    ($RemoteTagOutput | Out-String).Trim()
)

if ($RemoteTagExists) {
    throw "Tag $Tag already exists on origin. Refusing to overwrite a published release tag."
}

if ($LocalTag -eq $Tag) {
    Write-Host "Removing stale local tag $Tag." -ForegroundColor Yellow

    git tag -d $Tag

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to remove stale local tag $Tag."
    }
}

Run-Step "Stage changes" {
    git add -A
}

git diff --cached --quiet
$CachedDiffExitCode = $LASTEXITCODE

if ($CachedDiffExitCode -eq 0) {
    Write-Host ""
    Write-Host "==> No new changes to commit" -ForegroundColor Yellow
    Write-Host "Using current HEAD as the release commit." -ForegroundColor Yellow

    $ReleaseCommit = (git rev-parse --short HEAD | Out-String).Trim()
    $ReleaseMessage = (git log -1 --pretty=%s | Out-String).Trim()

    Write-Host ""
    Write-Host "Version: $Version" -ForegroundColor Cyan
    Write-Host "Commit:  $ReleaseCommit" -ForegroundColor Cyan
    Write-Host "Message: $ReleaseMessage" -ForegroundColor Cyan
    Write-Host "Tag:     $Tag" -ForegroundColor Cyan
}
elseif ($CachedDiffExitCode -eq 1) {
    if ([string]::IsNullOrWhiteSpace($Message)) {
        throw "There are changes to commit, but no commit message was specified."
    }

    Write-Host ""
    Write-Host "Version:        $Version" -ForegroundColor Cyan
    Write-Host "Commit message: $Message" -ForegroundColor Cyan
    Write-Host "Tag:            $Tag" -ForegroundColor Cyan

    Run-Step "Create release commit" {
        git commit -m $Message
    }

    $ReleaseCommit = (git rev-parse --short HEAD | Out-String).Trim()
    $ReleaseMessage = $Message
}
else {
    throw "Unable to determine staged changes (git diff exit code $CachedDiffExitCode)."
}

Run-Step "Create annotated tag $Tag" {
    git tag -a $Tag -m $TagMessage
}

if ($Push) {
    Run-Step "Push commit" {
        git push
    }

    Run-Step "Push tag $Tag" {
        git push origin $Tag
    }
}
else {
    Write-Host ""
    Write-Host "Release commit and tag created locally." -ForegroundColor Green
    Write-Host "To push them:" -ForegroundColor Yellow
    Write-Host "  git push"
    Write-Host "  git push origin $Tag"
}

Write-Host ""
Write-Host "Done: $ReleaseMessage ($Tag)" -ForegroundColor Green
