[CmdletBinding()]
param([Parameter(Mandatory)][ValidatePattern('^[a-z0-9][a-z0-9_-]*$')][string]$Scene, [switch]$VerifyOnly)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
$arguments = @('review-capture', '--scene', $Scene)
if ($VerifyOnly) { $arguments += '--verify-only' }
Invoke-TopicPython -Arguments $arguments
