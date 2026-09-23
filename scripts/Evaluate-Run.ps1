[CmdletBinding()]
param([Parameter(Mandatory)][string]$ConfigPath)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
$resolved = (Resolve-Path -LiteralPath $ConfigPath).Path
$runsRoot = (Join-Path $ArtifactRoot 'runs') + [IO.Path]::DirectorySeparatorChar
if (-not $resolved.StartsWith($runsRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Config must be inside $runsRoot"
}
$relative = $resolved.Substring($runsRoot.Length)
if ((Split-Path $relative -Leaf) -ne 'config.yml') { throw 'The input must be a Nerfstudio config.yml.' }
$runSlug = Split-Path $relative -Parent
$runDirectory = Split-Path $resolved -Parent
$checkpointDirectory = Join-Path $runDirectory 'nerfstudio_models'
if (-not (Test-Path -LiteralPath $checkpointDirectory) -or
    @(Get-ChildItem -LiteralPath $checkpointDirectory -Filter '*.ckpt' -File -ErrorAction SilentlyContinue).Count -eq 0) {
    throw "No training checkpoint exists beside $resolved"
}
$metricsDirectory = Join-Path $ArtifactRoot "metrics\$runSlug"
$metricsPath = Join-Path $metricsDirectory 'metrics.json'
$rendersPath = Join-Path $ArtifactRoot "renders\$runSlug"
New-TopicDirectory -Path $metricsDirectory
New-TopicDirectory -Path $rendersPath

Invoke-InEnvironment -Command 'ns-eval' -Arguments @('--load-config', $resolved, '--output-path', $metricsPath, '--render-output-path', $rendersPath) | Out-Null
$runBytes = (Get-ChildItem -LiteralPath $runDirectory -File -Recurse | Measure-Object Length -Sum).Sum
$runBytes | Set-Content -LiteralPath (Join-Path $metricsDirectory 'run-bytes.txt') -Encoding ascii

$metrics = Get-Content -LiteralPath $metricsPath -Raw | ConvertFrom-Json
$serialized = $metrics | ConvertTo-Json -Depth 20
if ($serialized -match '(?i)nan|infinity') { throw "Metrics contain a non-finite value: $metricsPath" }
if (@(Get-ChildItem -LiteralPath $rendersPath -File -Recurse).Count -eq 0) {
    throw "Evaluation produced no rendered held-out views: $rendersPath"
}
Write-TopicInfo "Metrics: $metricsPath"
Write-TopicInfo "Held-out renders: $rendersPath"
