[CmdletBinding()]
param([Parameter(Mandatory)][string]$Dataset)
. (Join-Path $PSScriptRoot 'lib\Common.ps1')
Invoke-TopicPython -Arguments @('prepare', '--scene', $Dataset)
