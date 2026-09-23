[CmdletBinding()]
param([ValidateSet('smoke', 'benchmark', 'all')][string]$Mode = 'smoke')

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell

function Get-SmokeDataset {
    $transform = Join-Path $RawDataRoot 'nerfstudio\poster\transforms.json'
    if (Test-Path -LiteralPath $transform) {
        Write-TopicInfo 'Poster smoke dataset already exists; skipping.'
        return
    }
    New-TopicDirectory -Path $RawDataRoot
    Invoke-InEnvironment -Command 'ns-download-data' -Arguments @('nerfstudio', '--save-dir', $RawDataRoot, '--capture-name', 'poster') | Out-Null
    if (-not (Test-Path -LiteralPath $transform)) { throw 'Poster download did not produce transforms.json.' }
}

function Expand-SelectedZipDirectories {
    param([string]$Archive, [string]$Destination, [string[]]$Directories)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        foreach ($entry in $zip.Entries) {
            $normalized = $entry.FullName -replace '\\', '/'
            $scene = $Directories | Where-Object { $normalized.StartsWith("$_/", [StringComparison]::Ordinal) } | Select-Object -First 1
            if (-not $scene) { continue }
            $target = Join-Path $Destination ($normalized -replace '/', '\')
            if ([string]::IsNullOrEmpty($entry.Name)) {
                New-TopicDirectory -Path $target
                continue
            }
            New-TopicDirectory -Path (Split-Path $target -Parent)
            $source = $entry.Open()
            $output = [System.IO.File]::Open($target, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
            try { $source.CopyTo($output) } finally { $output.Dispose(); $source.Dispose() }
        }
    } finally { $zip.Dispose() }
}

function Get-BenchmarkDataset {
    $freeGiB = Get-FreeSpaceGiB
    if ($freeGiB -lt $Config.MinimumDatasetFreeGiB) {
        throw "Benchmark setup requires at least $($Config.MinimumDatasetFreeGiB) GiB free; only $freeGiB GiB is available."
    }
    $cacheDirectory = Join-Path $DataRoot '.cache'
    $archive = Join-Path $cacheDirectory '360_v2.zip'
    $target = Join-Path $RawDataRoot 'mipnerf360'
    New-TopicDirectory -Path $cacheDirectory
    New-TopicDirectory -Path $target

    $validArchive = (Test-Path -LiteralPath $archive) -and ((Get-Item -LiteralPath $archive).Length -eq $Config.MipNerf360ArchiveBytes)
    if (-not $validArchive) {
        Write-TopicInfo 'Downloading the official 12.5 GB Mip-NeRF 360 archive (resume enabled).'
        & curl.exe --fail --location --retry 5 --retry-delay 3 --continue-at - --output $archive $Config.MipNerf360Url
        if ($LASTEXITCODE -ne 0) { throw 'Mip-NeRF 360 download failed. Rerun the same command to resume.' }
    }
    $actualBytes = (Get-Item -LiteralPath $archive).Length
    if ($actualBytes -ne $Config.MipNerf360ArchiveBytes) {
        throw "Archive size mismatch: expected $($Config.MipNerf360ArchiveBytes), got $actualBytes."
    }

    $missingScenes = @($Config.MipNerf360Scenes | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $target "$_\.topic16-extracted"))
    })
    foreach ($scene in $missingScenes) {
        Write-TopicInfo "Extracting $scene from the verified archive."
        Expand-SelectedZipDirectories -Archive $archive -Destination $target -Directories @($scene)
        foreach ($relative in @("$scene\images_2", "$scene\sparse\0")) {
            if (-not (Test-Path -LiteralPath (Join-Path $target $relative))) {
                throw "Unexpected archive layout: missing $relative"
            }
        }
        'verified archive extraction completed' | Set-Content -LiteralPath (Join-Path $target "$scene\.topic16-extracted") -Encoding ascii
    }
    foreach ($scene in $Config.MipNerf360Scenes) {
        foreach ($relative in @("$scene\images_2", "$scene\sparse\0")) {
            if (-not (Test-Path -LiteralPath (Join-Path $target $relative))) { throw "Unexpected archive layout: missing $relative" }
        }
    }
    Write-TopicInfo "Archive retained at $archive for reproducibility and cheap reruns."
}

if ($Mode -in @('smoke', 'all')) { Get-SmokeDataset }
if ($Mode -in @('benchmark', 'all')) { Get-BenchmarkDataset }
Write-TopicInfo "Dataset profile '$Mode' is ready."
