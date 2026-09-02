param(
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'

function Fail {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Fail "Git is not installed or is not available in PATH."
    }

    # Expected location:
    #
    #   <project>\scripts\export-git-project.ps1
    #
    # The project root is always the parent of the scripts directory.
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
    $ProjectName = Split-Path $ProjectRoot -Leaf

    # By default the archive is created next to the project directory.
    # This prevents old ZIP files from becoming part of later exports.
    if (-not $OutputDirectory) {
        $OutputDirectory = Split-Path $ProjectRoot -Parent
    }

    Ensure-Directory -Path $OutputDirectory
    $OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path

    $Timestamp = Get-Date -Format 'dd-MM-yyyy-HH-mm-ss'
    $ArchivePath = Join-Path $OutputDirectory "$ProjectName-$Timestamp.zip"

    if (Test-Path -LiteralPath $ArchivePath) {
        Fail "Archive already exists: $ArchivePath"
    }

    # No real .git directory is required.
    #
    # Git is used only as the parser for .gitignore rules.
    # Temporary Git metadata is created in %TEMP%, so the project itself
    # is not initialized, modified, staged or committed.
    $TempGitDir = Join-Path (
        [System.IO.Path]::GetTempPath()
    ) ("export-git-meta-" + [guid]::NewGuid().ToString('N'))

    $StagingDir = Join-Path (
        [System.IO.Path]::GetTempPath()
    ) ("export-git-stage-" + [guid]::NewGuid().ToString('N'))

    Ensure-Directory -Path $TempGitDir
    Ensure-Directory -Path $StagingDir

    try {
        & git `
            "--git-dir=$TempGitDir" `
            "--work-tree=$ProjectRoot" `
            init `
            --quiet

        if ($LASTEXITCODE -ne 0) {
            Fail "Temporary git init failed with exit code $LASTEXITCODE."
        }

        $Utf8 = New-Object System.Text.UTF8Encoding($false)
        $OldConsoleOutputEncoding = [Console]::OutputEncoding
        $OldOutputEncoding = $OutputEncoding

        try {
            [Console]::OutputEncoding = $Utf8
            $OutputEncoding = $Utf8

            # List every file that is NOT ignored by Git rules.
            #
            # This respects:
            #   - root .gitignore
            #   - nested .gitignore files
            #   - negation rules (!file)
            #   - directory rules
            #   - wildcard rules
            #
            # The real .git directory, if present, is always excluded.
            $Files = & git `
                -c core.quotepath=false `
                "--git-dir=$TempGitDir" `
                "--work-tree=$ProjectRoot" `
                ls-files `
                --others `
                --exclude-standard `
                '--exclude=.git/'

            $GitExitCode = $LASTEXITCODE
        }
        finally {
            [Console]::OutputEncoding = $OldConsoleOutputEncoding
            $OutputEncoding = $OldOutputEncoding
        }

        if ($GitExitCode -ne 0) {
            Fail "git ls-files failed with exit code $GitExitCode."
        }

        $CopiedCount = 0

        foreach ($RelativePath in $Files) {
            if ([string]::IsNullOrWhiteSpace($RelativePath)) {
                continue
            }

            $RelativePath = $RelativePath -replace '/', '\\'
            $SourcePath = Join-Path $ProjectRoot $RelativePath

            if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
                continue
            }

            $DestinationPath = Join-Path $StagingDir $RelativePath
            $DestinationDirectory = Split-Path $DestinationPath -Parent

            Ensure-Directory -Path $DestinationDirectory

            Copy-Item `
                -LiteralPath $SourcePath `
                -Destination $DestinationPath `
                -Force

            $CopiedCount++
        }

        if ($CopiedCount -eq 0) {
            Fail "No files found to archive in: $ProjectRoot"
        }

        Add-Type -AssemblyName System.IO.Compression.FileSystem

        [System.IO.Compression.ZipFile]::CreateFromDirectory(
            $StagingDir,
            $ArchivePath,
            [System.IO.Compression.CompressionLevel]::Optimal,
            $false
        )

        Write-Host ""
        Write-Host "Project : $ProjectRoot"
        Write-Host "Files   : $CopiedCount"
        Write-Host "ZIP     : $ArchivePath" -ForegroundColor Green
    }
    finally {
        if (Test-Path -LiteralPath $StagingDir) {
            Remove-Item -LiteralPath $StagingDir -Recurse -Force
        }

        if (Test-Path -LiteralPath $TempGitDir) {
            Remove-Item -LiteralPath $TempGitDir -Recurse -Force
        }
    }
}
catch {
    Fail $_.Exception.Message
}
