[CmdletBinding()]
param([ValidateSet('smoke', 'benchmark', 'all')][string]$Mode = 'smoke')

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell

function Get-SmokeDataset {
    $targetRoot = Join-Path $RawDataRoot 'nerfstudio'
    $posterRoot = Join-Path $targetRoot 'poster'
    $processedRoot = Join-Path $ProcessedDataRoot 'nerfstudio\poster'
    $transform = Join-Path $posterRoot 'transforms.json'
    $requiredPaths = @(
        $transform,
        (Join-Path $posterRoot 'images'),
        (Join-Path $posterRoot 'images_2'),
        (Join-Path $posterRoot 'sparse_pc.ply'),
        (Join-Path $posterRoot 'colmap\sparse\0\points3D.bin')
    )
    $processedTransform = Join-Path $processedRoot 'transforms.json'
    $processedFrames = @()
    if (Test-Path -LiteralPath $processedTransform) {
        try { $processedFrames = @((Get-Content -LiteralPath $processedTransform -Raw | ConvertFrom-Json).frames) }
        catch { Write-TopicInfo 'Processed poster metadata is invalid; rebuilding from raw data.' }
    }
    if ((Test-Path -LiteralPath $processedTransform) -and
        @(Get-ChildItem -LiteralPath (Join-Path $processedRoot 'images') -File -ErrorAction SilentlyContinue).Count -eq 100 -and
        @(Get-ChildItem -LiteralPath (Join-Path $processedRoot 'images_2') -File -ErrorAction SilentlyContinue).Count -eq 100 -and
        $processedFrames.Count -eq 100 -and
        (Test-Path -LiteralPath (Join-Path $processedRoot 'sparse_pc.ply')) -and
        @($processedFrames | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $processedRoot $_.file_path)) -or
            -not (Test-Path -LiteralPath (Join-Path (Join-Path $processedRoot 'images_2') (Split-Path $_.file_path -Leaf)))
        }).Count -eq 0) {
        Write-TopicInfo "Processed poster smoke dataset already valid (100 frames); skipping."
        return
    }

    # Data acquisition must work before the CUDA compiler/runtime is ready.
    $environmentPath = Get-CondaEnvironmentPath -Name $Config.EnvironmentName
    if (-not $environmentPath) {
        Write-TopicInfo "Creating minimal Python environment $($Config.EnvironmentName) for data acquisition."
        Invoke-Conda -Arguments @('create', '-n', $Config.EnvironmentName, '-y', "python=$($Config.PythonVersion)", 'pip<25') | Out-Null
    }
    Invoke-InEnvironment -Command 'python' -Arguments @(
        '-m', 'pip', 'install', "huggingface_hub==$($Config.HfHubVersion)"
    ) | Out-Null
    New-TopicDirectory -Path $targetRoot
    Write-TopicInfo "Downloading official Nerfstudio poster from $($Config.PosterRepository) at $($Config.PosterRevision)."
    $downloadSucceeded = $false
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        Write-TopicInfo "Poster download pass $attempt/12; existing files are reused."
        $exitCode = Invoke-InEnvironment -Command 'hf' -Arguments @(
            'download', $Config.PosterRepository, '--repo-type', 'dataset',
            '--revision', $Config.PosterRevision, '--include',
            'poster/transforms.json', 'poster/sparse_pc.ply',
            'poster/images/*', 'poster/images_2/*', 'poster/colmap/sparse/0/*',
            '--local-dir', $targetRoot, '--max-workers', '2'
        ) -AllowFailure
        if ($exitCode -eq 0) { $downloadSucceeded = $true; break }
        Start-Sleep -Seconds ([math]::Min(15, 2 * $attempt))
    }
    if (-not $downloadSucceeded) {
        throw 'Poster download did not finish after 12 resumable passes. Rerun this command later; partial files remain in the project.'
    }

    foreach ($path in $requiredPaths) {
        if (-not (Test-Path -LiteralPath $path)) { throw "Poster download is incomplete: missing $path" }
    }
    $metadata = Get-Content -LiteralPath $transform -Raw | ConvertFrom-Json
    $availableImages = @(Get-ChildItem -LiteralPath (Join-Path $posterRoot 'images') -File)
    $availableDownscaled = @(Get-ChildItem -LiteralPath (Join-Path $posterRoot 'images_2') -File)
    $fullNames = @{}; foreach ($file in $availableImages) { $fullNames[$file.Name] = $true }
    $downscaledNames = @{}; foreach ($file in $availableDownscaled) { $downscaledNames[$file.Name] = $true }
    $selectedFrames = @($metadata.frames | Where-Object {
        $name = Split-Path $_.file_path -Leaf
        $fullNames.ContainsKey($name) -and $downscaledNames.ContainsKey($name)
    })
    if ($selectedFrames.Count -ne 100 -or $availableImages.Count -ne 100 -or $availableDownscaled.Count -ne 100) {
        throw "Poster source is incomplete: matched=$($selectedFrames.Count), images=$($availableImages.Count), images_2=$($availableDownscaled.Count); expected 100 each."
    }
    # The pinned Hugging Face repository publishes 100 images but its metadata lists
    # 226 frames. Preserve raw data and materialize an explicit, valid smoke subset.
    New-TopicDirectory -Path $processedRoot
    foreach ($folder in @('images', 'images_2')) {
        $destination = Join-Path $processedRoot $folder
        New-TopicDirectory -Path $destination
        foreach ($file in (Get-ChildItem -LiteralPath (Join-Path $posterRoot $folder) -File)) {
            $target = Join-Path $destination $file.Name
            if (-not (Test-Path -LiteralPath $target) -or (Get-Item -LiteralPath $target).Length -ne $file.Length) {
                Copy-Item -LiteralPath $file.FullName -Destination $target -Force
            }
        }
    }
    Copy-Item -LiteralPath (Join-Path $posterRoot 'sparse_pc.ply') -Destination (Join-Path $processedRoot 'sparse_pc.ply') -Force
    $metadata.frames = $selectedFrames
    $metadata | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $processedTransform -Encoding utf8
    $validated = Get-Content -LiteralPath $processedTransform -Raw | ConvertFrom-Json
    if (@($validated.frames).Count -ne 100 -or
        @($validated.frames | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $processedRoot $_.file_path)) -or
            -not (Test-Path -LiteralPath (Join-Path (Join-Path $processedRoot 'images_2') (Split-Path $_.file_path -Leaf)))
        }).Count -ne 0) {
        throw 'Processed poster validation failed: a frame image is missing.'
    }
    Write-TopicInfo "Poster smoke subset validated at $processedRoot (100 frames from 226 metadata entries)."
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
