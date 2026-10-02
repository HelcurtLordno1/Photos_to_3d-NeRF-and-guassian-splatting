[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$validator = Join-Path $PSScriptRoot '..\scripts\Test-Datasets.ps1'
$fixtureRoot = Join-Path ([IO.Path]::GetTempPath()) ('topic16-data-' + [guid]::NewGuid().ToString('N'))
$manifestRoot = Join-Path $fixtureRoot 'manifests'
New-Item -ItemType Directory -Path $fixtureRoot | Out-Null
try {
    $failed = $false
    try { & $validator -Mode smoke -DatasetRoot $fixtureRoot -ManifestDirectory $manifestRoot -WriteManifest | Out-Null }
    catch { $failed = $true }
    if (-not $failed) { throw 'Missing poster dataset was accepted.' }
    if (Test-Path -LiteralPath $manifestRoot) { throw 'Invalid dataset created a manifest.' }
    Write-Host '[ok] Missing dataset rejected without a success manifest.'

    $config = Import-PowerShellDataFile (Join-Path $PSScriptRoot '..\configs\project.psd1')
    $raw = Join-Path $fixtureRoot 'raw\nerfstudio\poster'
    $processed = Join-Path $fixtureRoot 'processed\nerfstudio\poster'
    foreach ($root in @($raw, $processed)) {
        foreach ($folder in @('images', 'images_2')) {
            New-Item -ItemType Directory -Path (Join-Path $root $folder) -Force | Out-Null
        }
        'ply' | Set-Content -LiteralPath (Join-Path $root 'sparse_pc.ply')
    }
    Add-Type -AssemblyName System.Drawing
    $template = Join-Path $fixtureRoot 'template.png'
    $bitmap = New-Object System.Drawing.Bitmap 2,2
    try { $bitmap.Save($template, [System.Drawing.Imaging.ImageFormat]::Png) }
    finally { $bitmap.Dispose() }
    $frames = @()
    for ($index = 0; $index -lt $config.PosterRawFrameCount; $index++) {
        $name = '{0:D3}.png' -f $index
        $frames += @{ file_path = "images/$name" }
        if ($index -ge $config.PosterImageCount) { continue }
        foreach ($root in @($raw, $processed)) {
            foreach ($folder in @('images', 'images_2')) {
                Copy-Item -LiteralPath $template -Destination (Join-Path $root "$folder\$name")
            }
        }
    }
    @{ frames = $frames } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $raw 'transforms.json') -Encoding utf8
    $processedJson = @{ frames = @($frames | Select-Object -First $config.PosterImageCount) } | ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText((Join-Path $processed 'transforms.json'), $processedJson, (New-Object Text.UTF8Encoding($false)))
    & $validator -Mode smoke -DatasetRoot $fixtureRoot -ManifestDirectory $manifestRoot -WriteManifest | Out-Null
    $manifest = Join-Path $manifestRoot 'poster.json'
    if (-not (Test-Path -LiteralPath $manifest)) { throw 'Valid fixture did not create a manifest.' }
    $oldHash = (Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash
    $processedJson | Set-Content -LiteralPath (Join-Path $processed 'transforms.json') -Encoding utf8
    $failed = $false
    try { & $validator -Mode smoke -DatasetRoot $fixtureRoot -ManifestDirectory $manifestRoot -WriteManifest | Out-Null }
    catch { $failed = $true }
    if (-not $failed) { throw 'UTF-8 BOM incompatible with Nerfstudio was accepted.' }
    [IO.File]::WriteAllText((Join-Path $processed 'transforms.json'), $processedJson, (New-Object Text.UTF8Encoding($false)))
    Write-Host '[ok] Nerfstudio-incompatible UTF-8 BOM rejected.'
    'corrupt but nonempty' | Set-Content -LiteralPath (Join-Path $processed 'images_2\099.png')
    $failed = $false
    try { & $validator -Mode smoke -DatasetRoot $fixtureRoot -ManifestDirectory $manifestRoot -WriteManifest | Out-Null }
    catch { $failed = $true }
    if (-not $failed) { throw 'Corrupt nonempty image was accepted.' }
    if ((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash -ne $oldHash) {
        throw 'Invalid dataset changed the prior valid manifest.'
    }
    Write-Host '[ok] Corrupt image rejected; prior manifest preserved.'
} finally {
    Remove-Item -LiteralPath $fixtureRoot -Recurse -Force
}
