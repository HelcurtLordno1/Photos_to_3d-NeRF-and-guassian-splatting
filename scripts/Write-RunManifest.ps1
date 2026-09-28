[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$InputPath,
    [string]$ArtifactsDirectory
)

. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Assert-WindowsPowerShell
if (-not $ArtifactsDirectory) { $ArtifactsDirectory = $ArtifactRoot }
& (Join-Path $PSScriptRoot 'Test-RunManifest.ps1') -Path $InputPath
$manifest = Get-Content -LiteralPath $InputPath -Raw | ConvertFrom-Json
$parts = @($manifest.run_key -split '/')
if ($parts.Count -ne 3) { throw 'Run key must have exactly three components.' }
$logDirectory = Join-Path $ArtifactsDirectory "logs\$($parts[0])\$($parts[1])\$($parts[2])"
New-TopicDirectory -Path $logDirectory
$destination = Join-Path $logDirectory 'manifest.json'
if (Test-Path -LiteralPath $destination) {
    & (Join-Path $PSScriptRoot 'Test-RunManifest.ps1') -Path $destination
    $previous = Get-Content -LiteralPath $destination -Raw | ConvertFrom-Json
    if ($previous.run_key -cne $manifest.run_key) { throw 'Existing manifest has a different run key.' }
    if ($previous.status -ne 'running') { throw 'Completed run manifests are immutable.' }
    if ($manifest.status -eq 'running') { throw 'A running manifest already exists for this run key.' }
}
$temporary = Join-Path $logDirectory ('.manifest-' + [guid]::NewGuid().ToString('N') + '.tmp')
$backup = Join-Path $logDirectory ('.manifest-' + [guid]::NewGuid().ToString('N') + '.bak')
try {
    Copy-Item -LiteralPath $InputPath -Destination $temporary
    if (Test-Path -LiteralPath $destination) {
        [System.IO.File]::Replace($temporary, $destination, $backup)
    } else {
        Move-Item -LiteralPath $temporary -Destination $destination
    }
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
}
Write-TopicInfo "Run manifest saved: $destination"
