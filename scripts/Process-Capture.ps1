[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9][a-z0-9_-]*$')][string]$Scene,
    [Parameter(Mandatory)][string]$TrainImages,
    [Parameter(Mandatory)][string]$EvalImages
)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
$trainPath = (Resolve-Path -LiteralPath $TrainImages).Path
$evalPath = (Resolve-Path -LiteralPath $EvalImages).Path
$imageExtensions = @('.jpg', '.jpeg', '.png', '.tif', '.tiff')
$trainFiles = @(Get-ChildItem -LiteralPath $trainPath -File | Where-Object { $_.Extension.ToLowerInvariant() -in $imageExtensions })
$evalFiles = @(Get-ChildItem -LiteralPath $evalPath -File | Where-Object { $_.Extension.ToLowerInvariant() -in $imageExtensions })
if ($trainFiles.Count -lt 8) { throw 'At least eight training images are required for a custom scene.' }
if ($evalFiles.Count -lt 1) { throw 'At least one held-out evaluation image is required.' }
$trainHashes = @{}
foreach ($file in $trainFiles) { $trainHashes[(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash] = $true }
foreach ($file in $evalFiles) {
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    if ($trainHashes.ContainsKey($hash)) { throw "Training/evaluation image is duplicated: $($file.FullName)" }
}
$output = Join-Path $ProcessedDataRoot "custom\$Scene"
if (Test-Path -LiteralPath (Join-Path $output 'transforms.json')) {
    throw "Processed scene already exists at $output; use a new scene name to preserve provenance."
}
New-TopicDirectory -Path $output
$arguments = @('images', '--data', $trainPath, '--output-dir', $output, '--eval-data', $evalPath)
Write-TopicInfo "Running COLMAP-backed preprocessing for $Scene."
Invoke-InEnvironment -Command 'ns-process-data' -Arguments $arguments | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $output 'transforms.json'))) { throw 'Preprocessing did not produce transforms.json.' }
Write-TopicInfo "Processed capture ready: $output"
