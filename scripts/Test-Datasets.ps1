[CmdletBinding()]
param(
    [ValidateSet('smoke', 'benchmark', 'all')][string]$Mode = 'all',
    [string]$DatasetRoot,
    [string]$ManifestDirectory,
    [switch]$WriteManifest
)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
Add-Type -AssemblyName System.Drawing
if (-not $DatasetRoot) { $DatasetRoot = $DataRoot }
if (-not $ManifestDirectory) { $ManifestDirectory = Join-Path $ArtifactRoot 'logs\datasets' }

function Assert-File {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing dataset file: $Path" }
    if ((Get-Item -LiteralPath $Path).Length -eq 0) { throw "Empty dataset file: $Path" }
}

function Get-Resolution {
    param([string]$ImagePath)
    $image = [System.Drawing.Image]::FromFile($ImagePath)
    try { return @{ width = $image.Width; height = $image.Height } }
    finally { $image.Dispose() }
}

function Write-SceneManifest {
    param($Record)
    if (-not $WriteManifest) { return }
    New-TopicDirectory -Path $ManifestDirectory
    $destination = Join-Path $ManifestDirectory "$($Record.scene).json"
    $temporary = Join-Path $ManifestDirectory (".$($Record.scene)-$([guid]::NewGuid().ToString('N')).tmp")
    try {
        $Record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temporary -Encoding utf8
        Move-Item -LiteralPath $temporary -Destination $destination -Force
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
    Write-TopicInfo "Scene manifest: $destination"
}

if ($Mode -in @('smoke', 'all')) {
    $raw = Join-Path $DatasetRoot 'raw\nerfstudio\poster'
    $processed = Join-Path $DatasetRoot 'processed\nerfstudio\poster'
    $transform = Join-Path $processed 'transforms.json'
    Assert-File $transform
    Assert-File (Join-Path $raw 'transforms.json')
    Assert-File (Join-Path $raw 'sparse_pc.ply')
    Assert-File (Join-Path $processed 'sparse_pc.ply')
    $rawFrames = @((Get-Content -LiteralPath (Join-Path $raw 'transforms.json') -Raw | ConvertFrom-Json).frames)
    $frames = @((Get-Content -LiteralPath $transform -Raw | ConvertFrom-Json).frames)
    $images = @(Get-ChildItem -LiteralPath (Join-Path $processed 'images') -File)
    $downscaled = @(Get-ChildItem -LiteralPath (Join-Path $processed 'images_2') -File)
    $rawImages = @(Get-ChildItem -LiteralPath (Join-Path $raw 'images') -File)
    $rawDownscaled = @(Get-ChildItem -LiteralPath (Join-Path $raw 'images_2') -File)
    $expected = $Config.PosterImageCount
    if ($rawFrames.Count -ne $Config.PosterRawFrameCount -or $frames.Count -ne $expected -or
        $images.Count -ne $expected -or $downscaled.Count -ne $expected -or
        $rawImages.Count -ne $expected -or $rawDownscaled.Count -ne $expected) {
        throw "Poster count mismatch: raw frames=$($rawFrames.Count), processed=$($frames.Count), images=$($images.Count), images_2=$($downscaled.Count); expected processed=$expected."
    }
    foreach ($frame in $frames) {
        $name = Split-Path $frame.file_path -Leaf
        Assert-File (Join-Path $processed $frame.file_path)
        $downscaledPath = Join-Path (Join-Path $processed 'images_2') $name
        Assert-File $downscaledPath
        Assert-File (Join-Path (Join-Path $raw 'images') $name)
        Assert-File (Join-Path (Join-Path $raw 'images_2') $name)
        [void](Get-Resolution $downscaledPath)
    }
    $record = [ordered]@{
        schema_version = '1.0'; scene = 'poster'
        source_url = "https://huggingface.co/datasets/$($Config.PosterRepository)"
        source_revision = $Config.PosterRevision
        raw_path = 'data/raw/nerfstudio/poster'
        processed_path = 'data/processed/nerfstudio/poster'
        image_count = $frames.Count
        resolution_images_2 = (Get-Resolution (Join-Path (Join-Path $processed 'images_2') (Split-Path $frames[0].file_path -Leaf)))
        sparse_files = @('sparse_pc.ply')
        downscale_factor = $Config.DownscaleFactor
        validated_at_utc = [DateTime]::UtcNow.ToString('o')
    }
    Write-SceneManifest $record
    Write-TopicInfo "Poster data validated ($($frames.Count) frames)."
}

if ($Mode -in @('benchmark', 'all')) {
    $archive = Join-Path $DatasetRoot '.cache\360_v2.zip'
    Assert-File $archive
    $bytes = (Get-Item -LiteralPath $archive).Length
    if ($bytes -ne $Config.MipNerf360ArchiveBytes) {
        throw "Mip-NeRF 360 archive size mismatch: expected $($Config.MipNerf360ArchiveBytes), got $bytes."
    }
    $sha256 = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sha256 -cne $Config.MipNerf360ArchiveSha256) {
        throw "Mip-NeRF 360 archive SHA-256 mismatch: expected $($Config.MipNerf360ArchiveSha256), got $sha256. Keep the file for diagnosis; do not train from it."
    }
    foreach ($scene in $Config.MipNerf360Scenes) {
        $root = Join-Path $DatasetRoot "raw\mipnerf360\$scene"
        $images = @(Get-ChildItem -LiteralPath (Join-Path $root 'images_2') -File)
        $expected = $Config.MipNerf360ImageCounts[$scene]
        if ($images.Count -ne $expected) { throw "$scene images_2 count mismatch: expected $expected, got $($images.Count)." }
        foreach ($image in $images) {
            Assert-File $image.FullName
            [void](Get-Resolution $image.FullName)
        }
        $sparse = @('cameras.bin', 'images.bin', 'points3D.bin')
        foreach ($name in $sparse) { Assert-File (Join-Path $root "sparse\0\$name") }
        $record = [ordered]@{
            schema_version = '1.0'; scene = $scene
            source_url = $Config.MipNerf360Url
            archive_bytes = $bytes
            archive_sha256 = $sha256
            raw_path = "data/raw/mipnerf360/$scene"
            image_count = $images.Count
            resolution_images_2 = (Get-Resolution $images[0].FullName)
            sparse_files = @($sparse | ForEach-Object { "sparse/0/$_" })
            downscale_factor = $Config.DownscaleFactor
            validated_at_utc = [DateTime]::UtcNow.ToString('o')
        }
        Write-SceneManifest $record
        Write-TopicInfo "$scene data validated ($($images.Count) images)."
    }
}
Write-TopicInfo "Dataset validation '$Mode' passed."
