[CmdletBinding()]
param(
    [string]$SourceDirectory = '',
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
if (-not $SourceDirectory) { $SourceDirectory = Join-Path $projectRoot 'docs\assets' }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $projectRoot 'docs\assets-optimized' }
$source = (Resolve-Path -LiteralPath $SourceDirectory).Path
$target = [IO.Path]::GetFullPath($OutputDirectory)
if ($source.TrimEnd('\') -eq $target.TrimEnd('\')) { throw 'Source and output directories must differ.' }

Get-ChildItem $source -Recurse -File |
Where-Object { $_.Extension.ToLower() -in @(".png", ".jpg", ".jpeg", ".gif", ".mp4") } |
ForEach-Object {
    $file = $_
    $relative = $file.FullName.Substring($source.TrimEnd('\').Length).TrimStart('\')
    $destination = Join-Path $target $relative
    $folder = Split-Path $destination -Parent

    New-Item -ItemType Directory -Force -Path $folder | Out-Null

    $output = switch ($file.Extension.ToLower()) {
        ".png" { [IO.Path]::ChangeExtension($destination, ".webp") }
        ".gif" { [IO.Path]::ChangeExtension($destination, ".webp") }
        ".jpg"  { [IO.Path]::ChangeExtension($destination, ".webp") }
        ".jpeg" { [IO.Path]::ChangeExtension($destination, ".webp") }
        ".mp4" { $destination }
    }

    if (Test-Path -LiteralPath $output -PathType Leaf) {
        Write-Host "Keeping existing optimized file: $relative"
        return
    }

    Write-Host "Compressing: $relative"

    switch ($file.Extension.ToLower()) {
        ".png" {
            & ffmpeg -hide_banner -loglevel error -n `
                -i $file.FullName `
                -c:v libwebp -quality 85 -compression_level 6 `
                $output
        }
        ".gif" {
            & ffmpeg -hide_banner -loglevel error -n `
                -i $file.FullName `
                -c:v libwebp_anim -quality 80 -compression_level 6 `
                -loop 0 -an `
                $output
        }
        { $_ -in ".jpg", ".jpeg" } {
            & ffmpeg -hide_banner -loglevel error -n `
                -i $file.FullName `
                -c:v libwebp -quality 85 -compression_level 6 `
                $output
        }
        ".mp4" {
            & ffmpeg -hide_banner -loglevel error -n `
                -i $file.FullName `
                -c:v libx264 -preset slow -crf 23 `
                -pix_fmt yuv420p -c:a aac -b:a 128k `
                -movflags +faststart `
                $output
        }
    }

    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $output)) {
        $oldSize = $file.Length
        $newSize = (Get-Item -LiteralPath $output).Length
        $saved = if ($oldSize -gt 0) {
            [math]::Round((1 - $newSize / $oldSize) * 100, 1)
        } else { 0 }

        Write-Host "Saved: $saved%"
    } else {
        throw "Failed: $relative"
    }
}
