[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-z0-9][a-z0-9_-]*$')][string]$Scene,
    [Parameter(Mandatory)][string]$Reviewer,
    [Parameter(Mandatory)][string]$Notes
)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Invoke-TopicPython -Arguments @('approve-capture', '--scene', $Scene, '--reviewer', $Reviewer, '--notes', $Notes)
