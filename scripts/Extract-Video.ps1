[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Video,
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9][a-z0-9_-]*$')][string]$Scene,
    [ValidateRange(16, 10000)][int]$FrameCount
)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
$arguments = @('extract-video', '--video', (Resolve-Path -LiteralPath $Video).Path, '--scene', $Scene)
if ($PSBoundParameters.ContainsKey('FrameCount')) { $arguments += @('--frames', [string]$FrameCount) }
Invoke-TopicPython -Arguments $arguments
