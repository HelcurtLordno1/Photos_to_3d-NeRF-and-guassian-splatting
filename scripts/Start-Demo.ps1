[CmdletBinding()]
param([Parameter(Mandatory)][string]$ModelPath, [switch]$HealthOnly, [switch]$Fallback)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
$arguments = @('demo', '--model', (Resolve-Path -LiteralPath $ModelPath).Path)
if ($HealthOnly) { $arguments += '--health-only' }
if ($Fallback) { $arguments += '--fallback' }
Invoke-TopicPython -Arguments $arguments
