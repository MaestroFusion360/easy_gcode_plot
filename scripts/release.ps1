param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [Parameter(Mandatory = $true)]
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
        -File ".\scripts\lint.ps1" `
        -Fix

    $LintExitCode = $LASTEXITCODE

    if ($LintExitCode -ne 0) {
        Write-Host ""
        Write-Host "Lint reported issues (exit code $LintExitCode)." -ForegroundColor Yellow
        Write-Host "Release continues." -ForegroundColor Yellow
    }
    else {
        Write-Host "Lint completed successfully." -ForegroundColor Green
    }

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

if ([string]::IsNullOrWhiteSpace($Message)) {
    throw "Commit message must not be empty."
}

Run-Lint

Run-Step "Tests" {
    & ".\scripts\test.ps1"
}

Run-Step "git diff --check" {
    git diff --check
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
    git add .
}

git diff --cached --quiet

if ($LASTEXITCODE -eq 0) {
    throw "There are no staged changes to commit."
}

Write-Host ""
Write-Host "Version:        $Version" -ForegroundColor Cyan
Write-Host "Commit message: $Message" -ForegroundColor Cyan
Write-Host "Tag:            $Tag" -ForegroundColor Cyan

Run-Step "Create release commit" {
    git commit -m $Message
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
Write-Host "Done: $Message ($Tag)" -ForegroundColor Green