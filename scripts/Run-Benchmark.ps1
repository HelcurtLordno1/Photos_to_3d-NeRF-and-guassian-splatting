[CmdletBinding()]
param(
    [string[]]$Scenes = @('bonsai', 'garden', 'room'),
    [string]$MatrixPath,
    [switch]$Resume,
    [ValidateSet('primary', 'diagnostic', 'repeat')][string]$Protocol = 'primary',
    [ValidateRange(1, 2147483647)][int]$Iterations,
    [int]$Seed
)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
if (-not $MatrixPath) {
    if ($Resume) { throw '-Resume requires an explicit -MatrixPath.' }
    $MatrixPath = Join-Path $ArtifactRoot ('logs\matrices\' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '.json')
}
$arguments = @('benchmark', '--matrix', [IO.Path]::GetFullPath($MatrixPath), '--protocol', $Protocol, '--scenes') + $Scenes
if ($Resume) { $arguments += '--resume' }
if ($PSBoundParameters.ContainsKey('Iterations')) { $arguments += @('--iterations', [string]$Iterations) }
if ($PSBoundParameters.ContainsKey('Seed')) { $arguments += @('--seed', [string]$Seed) }
Write-TopicInfo "Explicit matrix for resume: $MatrixPath"
Invoke-TopicPython -Arguments $arguments
